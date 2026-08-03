from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from apps.core.ratelimit import ratelimit_or_503
import logging

from .models import CustomUser, PasswordResetLog
from .serializers import (
    UserSerializer, UserCreateSerializer,
    ChangePasswordSerializer, CustomTokenObtainPairSerializer,
    AdminResetPasswordSerializer,
)
from .permissions import IsAdminOrAbove, CanManageUser
from apps.core.tenancy import get_request_school

logger = logging.getLogger("apps")


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    @ratelimit_or_503(key="ip", rate="20/m", method="POST")
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            logger.info(f"Login: {request.data.get('email', '?')}")
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            rt = request.data.get("refresh")
            if rt:
                RefreshToken(rt).blacklist()
            logger.info(f"Logout: {request.user.email}")
            return Response({"detail": "Déconnexion réussie."})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        """PATCH /api/auth/me/ — update own profile."""
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        # Only allow safe fields (not role, not email uniqueness issues without careful handling)
        allowed = ["first_name", "last_name", "phone", "avatar", "preferred_language"]
        data = {k: v for k, v in request.data.items() if k in allowed}
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        logger.info(f"Profile updated: {instance.email}")
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data["new_password"])
            # Fin du parcours « mot de passe temporaire » : l'utilisateur a
            # choisi son propre mot de passe, l'obligation est levée.
            request.user.must_change_password = False
            request.user.save()
            logger.info(f"Password changed (self): {request.user.email}")
            return Response({"detail": "Mot de passe modifié."})
        return Response(serializer.errors, status=400)


class UserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def get_serializer_class(self):
        return UserCreateSerializer if self.request.method == "POST" else UserSerializer

    def get_queryset(self):
        user = self.request.user
        qs = CustomUser.objects.all()
        if user.is_superadmin():
            school = get_request_school(self.request)
            if school is not None:
                qs = qs.filter(school=school)
            # sans ?school_id= : vue plateforme globale (tous tenants)
        elif user.is_admin():
            qs = qs.filter(role_level__lt=user.role_level, school=user.school)
        else:
            return CustomUser.objects.none()
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        # FIX v37 (vidéo 1) : ?unlinked=1 — ne renvoyer que les comptes SANS
        # profil déjà associé (student_profile / teacher_profile / parent_profile
        # selon le rôle). Le formulaire « Nouvel élève » proposait des comptes
        # déjà liés (ex: eleve5 → élève 0005), menant à une erreur d'intégrité
        # OneToOne au lieu d'un parcours de réinscription.
        if self.request.query_params.get("unlinked") in ("1", "true", "True"):
            profile_map = {
                "student": "student_profile",
                "teacher": "teacher_profile",
                "parent": "parent_profile",
            }
            rel = profile_map.get(role)
            if rel:
                qs = qs.filter(**{f"{rel}__isnull": True})
        # BUG FIX: Allow filtering by is_active for user pickers (teacher create form etc.)
        is_active_param = self.request.query_params.get("is_active")
        if is_active_param is not None:
            qs = qs.filter(is_active=is_active_param in ("true", "1", "True"))
        # Ordering
        qs = qs.order_by("last_name", "first_name")
        return qs

    def perform_create(self, serializer):
        user = serializer.save()
        logger.info(f"User created: {user.email} by {self.request.user.email}")


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, CanManageUser]

    def get_queryset(self):
        user = self.request.user
        if user.is_superadmin():
            school = get_request_school(self.request)
            if school is not None:
                return CustomUser.objects.filter(school=school)
            # superadmin sans ?school_id= : vue transverse de gestion
            # plateforme (liste de TOUS les comptes).
            # ⚠️  Usage réservé aux endpoints /api/platform/ et à la
            # console d'administration interne. Ne pas exposer ce cas
            # à un frontend orienté établissement.
            return CustomUser.objects.select_related("school").all()
        if user.is_admin():
            return CustomUser.objects.filter(role_level__lt=user.role_level, school=user.school)
        return CustomUser.objects.none()


class ToggleUserActiveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    def post(self, request, pk):
        try:
            if request.user.is_superadmin():
                target = CustomUser.objects.get(pk=pk)
            else:
                target = CustomUser.objects.get(
                    pk=pk, role_level__lt=request.user.role_level, school=request.user.school,
                )
        except CustomUser.DoesNotExist:
            return Response({"detail": "Introuvable ou accès refusé."}, status=404)
        target.is_active = not target.is_active
        target.save()  # signal sync_user_to_entities handles Student.is_active

        # BUG FIX: Explicit propagation for Teacher/Parent (no is_active field on model,
        # but their user.is_active now correctly reflects in all filtered querysets).
        # For Student: the signal above already propagates. Belt-and-suspenders below.
        if target.role == "student":
            try:
                student = target.student_profile
                if student.is_active != target.is_active:
                    student.is_active = target.is_active
                    student.save(update_fields=["is_active"])
                    logger.info(
                        f"ToggleUserActive: Student {student} is_active={target.is_active}"
                    )
            except Exception as e:
                logger.warning(f"ToggleUserActive student sync error: {e}")

        state = "activé" if target.is_active else "désactivé"
        action_detail = f"Compte {state}."
        if target.role == "student":
            action_detail += " Profil élève synchronisé."
        logger.info(
            f"ToggleUserActive: {target.email} -> is_active={target.is_active} "
            f"by {request.user.email}"
        )
        return Response({"detail": action_detail, "is_active": target.is_active})


class AdminResetPasswordView(APIView):
    """
    POST /api/auth/users/<pk>/reset-password/  (P2 v4)

    Réinitialisation du mot de passe d'un utilisateur par un administrateur
    autorisé. Règles appliquées CÔTÉ BACKEND (jamais uniquement frontend) :
      - admin      → teacher / parent / student de SON établissement ;
      - superadmin → admin / teacher / parent / student (jamais superadmin) ;
      - jamais soi-même (parcours « changer mon mot de passe » distinct).

    Effets :
      - mot de passe haché par Django (set_password), jamais stocké en clair ;
      - must_change_password=True → nouveau mot de passe obligatoire à la
        prochaine connexion de la cible ;
      - révocation de tous les refresh tokens JWT de la cible (les sessions
        actives expirent avec l'access token, ≤ durée de vie configurée) —
        l'auteur de l'opération, lui, reste connecté ;
      - journal d'audit PasswordResetLog (auteur, cible, rôle, date —
        JAMAIS le mot de passe) ;
      - la réponse API ne renvoie JAMAIS le mot de passe.
    """
    permission_classes = [IsAuthenticated, IsAdminOrAbove]

    @ratelimit_or_503(key="user", rate="10/m", method="POST")
    def post(self, request, pk):
        requester = request.user
        try:
            target = CustomUser.objects.get(pk=pk)
        except CustomUser.DoesNotExist:
            return Response({"detail": "Utilisateur introuvable."}, status=404)

        # Contrôle d'accès vertical (rôles) ET horizontal (établissement).
        # Un 403 explicite (plutôt qu'un 404) : l'action est journalisée et
        # le frontend n'affiche l'action que sur les cibles autorisées.
        if not requester.can_reset_password_of(target):
            logger.warning(
                "Password reset REFUSÉ : %s (%s) → %s (%s)",
                requester.email, requester.role, target.email, target.role,
            )
            return Response(
                {"detail": "Vous n'êtes pas autorisé à réinitialiser le mot de passe de cet utilisateur."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AdminResetPasswordSerializer(
            data=request.data, context={"request": request, "target_user": target},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        target.set_password(serializer.validated_data["new_password"])
        target.must_change_password = True
        target.save()

        # Révocation des sessions : blacklist de TOUS les refresh tokens en
        # circulation pour la cible. L'ancien mot de passe ne permet plus de
        # se connecter et les sessions ne peuvent plus se renouveler.
        revoked = 0
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                OutstandingToken, BlacklistedToken,
            )
            for token in OutstandingToken.objects.filter(user=target):
                _, created = BlacklistedToken.objects.get_or_create(token=token)
                revoked += 1 if created else 0
        except Exception as exc:
            logger.warning("Révocation des tokens impossible : %s", exc)

        PasswordResetLog.objects.create(
            performed_by=requester,
            target_user=target,
            performed_by_email=requester.email,
            target_email=target.email,
            target_role=target.role,
            school=target.school,
        )
        # Journal applicatif — AUCUNE donnée sensible.
        logger.info(
            "Password reset : %s (%s) → %s (%s), %d refresh token(s) révoqué(s)",
            requester.email, requester.role, target.email, target.role, revoked,
        )
        return Response({
            "detail": (
                f"Mot de passe de {target.get_full_name()} réinitialisé. "
                "L'utilisateur devra choisir un nouveau mot de passe à sa prochaine connexion."
            ),
            "must_change_password": True,
        })


class MessageRecipientsView(APIView):
    """GET /api/auth/recipients/ — list users that can receive messages from this user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = CustomUser.objects.filter(is_active=True).exclude(id=user.id)
        if not user.is_superadmin():
            qs = qs.filter(school=user.school)
        if user.role_level >= 80:
            # admin / superadmin: can message anyone (dans son établissement)
            pass
        elif user.is_teacher():
            # teacher: can message admins and parents of their students
            from apps.parents.models import Parent
            parent_ids = Parent.objects.filter(
                children_links__student__current_class__in=user.teacher_profile.classes.all()
            ).values_list("user_id", flat=True).distinct()
            admin_ids = CustomUser.objects.filter(role_level__gte=80).values_list("id", flat=True)
            from django.db.models import Q
            qs = qs.filter(Q(id__in=parent_ids) | Q(id__in=admin_ids))
        elif user.is_parent():
            # parent: can message admins and teachers of their children
            try:
                classes = [ps.student.current_class for ps in user.parent_profile.children_links.select_related("student__current_class").all() if ps.student.current_class]
                from apps.teachers.models import Teacher
                teacher_ids = Teacher.objects.filter(classes__in=classes).values_list("user_id", flat=True).distinct()
                admin_ids = CustomUser.objects.filter(role_level__gte=80).values_list("id", flat=True)
                from django.db.models import Q
                qs = qs.filter(Q(id__in=teacher_ids) | Q(id__in=admin_ids))
            except Exception:
                qs = qs.filter(role_level__gte=80)
        elif user.is_student():
            # student: can message admins and their teachers
            try:
                cls = user.student_profile.current_class
                from apps.teachers.models import Teacher
                teacher_ids = Teacher.objects.filter(classes=cls).values_list("user_id", flat=True).distinct()
                admin_ids = CustomUser.objects.filter(role_level__gte=80).values_list("id", flat=True)
                from django.db.models import Q
                qs = qs.filter(Q(id__in=teacher_ids) | Q(id__in=admin_ids))
            except Exception:
                qs = qs.filter(role_level__gte=80)

        data = [{"id": u.id, "first_name": u.first_name, "last_name": u.last_name,
                 "full_name": u.get_full_name(), "email": u.email, "role": u.role}
                for u in qs.order_by("last_name", "first_name")]
        return Response(data)

class AvatarUploadView(APIView):
    """
    POST /api/auth/avatar/  — upload or replace avatar (multipart)
    DELETE /api/auth/avatar/ — delete avatar (restore fallback initials)
    """
    permission_classes = [IsAuthenticated]
    parser_classes_upload = None  # set dynamically

    def post(self, request):
        from rest_framework.parsers import MultiPartParser
        avatar = request.FILES.get("avatar")
        if not avatar:
            return Response({"error": "Aucun fichier fourni."}, status=400)
        # Delete old avatar file from storage
        user = request.user
        if user.avatar:
            try:
                user.avatar.delete(save=False)
            except Exception as exc:
                logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
        user.avatar = avatar
        user.save(update_fields=["avatar"])
        from .serializers import UserSerializer
        return Response(UserSerializer(user, context={"request": request}).data)

    def delete(self, request):
        user = request.user
        if user.avatar:
            try:
                user.avatar.delete(save=False)
            except Exception as exc:
                logger.warning("Erreur non bloquante ignorée : %s", exc, exc_info=True)
            user.avatar = None
            user.save(update_fields=["avatar"])
        from .serializers import UserSerializer
        return Response(UserSerializer(user, context={"request": request}).data)
