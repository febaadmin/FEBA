"""
apps/accounts/serializers.py — v29.2

Corrections v29.2 :
  - UserCreateSerializer : auto-génération d'un username unique côté
    BACKEND (plus de dépendance fragile au split("@")[0] frontend qui
    créait des doublons). Le username est maintenant généré à partir de
    l'email de façon garantie unique : base = email.split("@")[0],
    suffixe numérique si nécessaire.
  - Gestion d'erreur exhaustive : le handler extract_error() normalise
    toutes les erreurs DRF (dict, list, string) en un message unique et
    compréhensible, exposé directement au frontend.
  - Le champ `username` disparaît du payload attendu par le frontend :
    il n'a aucune valeur métier, c'est un artefact Django qu'on gère
    côté backend.
"""
import logging
import re
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from .models import CustomUser
from apps.core.academy_serializers import ACADEMY_FIELDS, AcademyMetadataMixin

logger = logging.getLogger("apps.accounts")

ADMIN_ALLOWED_ROLES = {"teacher", "parent", "student"}


def generate_unique_username(email: str) -> str:
    """
    Génère un username unique à partir d'un email.
    1. Base = partie locale de l'email, nettoyée (alphanum + underscore)
    2. Si déjà pris, ajoute un suffixe numérique (base_2, base_3, ...)
    """
    base = re.sub(r"[^a-zA-Z0-9_]", "_", email.split("@")[0])[:28] or "user"
    username = base
    counter = 2
    while CustomUser.objects.filter(username=username).exists():
        username = f"{base}_{counter}"
        counter += 1
        if counter > 9999:  # garde-fou théorique
            import uuid
            username = f"user_{uuid.uuid4().hex[:8]}"
            break
    return username


def extract_api_error(exc) -> str:
    """
    Extrait le premier message d'erreur compréhensible d'une exception DRF.
    Supporte : dict (ValidationError), list, string, et response.data.
    Retourne toujours une chaîne non vide et lisible.
    """
    try:
        data = exc.detail if hasattr(exc, "detail") else str(exc)
        if isinstance(data, dict):
            for key, val in data.items():
                msg = val[0] if isinstance(val, list) else str(val)
                if key == "non_field_errors":
                    return str(msg)
                return f"{msg}"
        if isinstance(data, list) and data:
            return str(data[0])
        return str(data)
    except Exception:
        return "Erreur interne du serveur."


# ── Lecture ────────────────────────────────────────────────────────────────────

class UserSerializer(AcademyMetadataMixin, serializers.ModelSerializer):
    # P3 : chaque objet expose son académie, sans quoi la vue
    # « Toutes les Académies » ne peut pas étiqueter ses lignes.
    academy_source = "school"
    full_name = serializers.SerializerMethodField()
    role_level = serializers.IntegerField(read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True, default=None)
    # FIX v42 : DRF ImageField renvoie une URL ABSOLUE quand la requête est
    # dans le contexte (request.build_absolute_uri), donnant en dev
    # « http://backend-dev:8000/media/... » — hôte interne Docker irrésoluble
    # par le navigateur (ERR_NAME_NOT_RESOLVED). On renvoie un chemin RELATIF
    # (« /media/... ») qui se résout via le proxy Vite (dev) ou Nginx (prod).
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj):
        try:
            return obj.avatar.url if obj.avatar else None
        except Exception:
            return None

    class Meta:
        model = CustomUser
        fields = [
            "id", "email", "username", "first_name", "last_name",
            "full_name", "role", "role_level", "phone", "avatar",
            "school", "school_name", "preferred_language",
            "is_active", "must_change_password", "created_at", "updated_at",
        ] + ACADEMY_FIELDS
        read_only_fields = ["id", "role_level", "must_change_password", "created_at", "updated_at"]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def validate_role(self, value):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return value
        requester = request.user
        if requester.is_superadmin():
            return value
        if requester.is_admin() and value not in ADMIN_ALLOWED_ROLES:
            raise serializers.ValidationError(
                "Vous ne pouvez pas attribuer ce rôle."
            )
        return value

    def validate_school(self, value):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return value
        requester = request.user
        if requester.is_superadmin():
            return value
        if value is not None and value != requester.school:
            raise serializers.ValidationError(
                "Vous ne pouvez pas assigner un utilisateur à un autre établissement."
            )
        return value


# ── Création ───────────────────────────────────────────────────────────────────

class UserCreateSerializer(serializers.ModelSerializer):
    """
    Sérializer de création.

    Points clés :
    - `username` n'est PAS dans les fields exposés au frontend : il est
      auto-généré côté backend de façon garantie unique. Le frontend
      n'a pas à gérer ce détail technique Django.
    - `school` injecté via __init__ pour éviter l'AssertionError DRF
      (PrimaryKeyRelatedField ne peut pas avoir queryset=None au niveau
      de la déclaration de classe).
    - Les erreurs de validation sont normalisées par DRF et renvoyées
      au frontend avec des champs explicites (email, password, role...).
    """
    password  = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        error_messages={"required": "Le mot de passe est obligatoire."},
    )
    password2 = serializers.CharField(
        write_only=True,
        error_messages={"required": "La confirmation du mot de passe est obligatoire."},
    )

    class Meta:
        model  = CustomUser
        # username INTENTIONNELLEMENT absent : généré automatiquement côté backend
        fields = [
            "email", "first_name", "last_name",
            "role", "phone", "password", "password2", "school",
        ]
        extra_kwargs = {
            "email":      {"error_messages": {"required": "L'email est obligatoire.", "invalid": "Format d'email invalide."}},
            "first_name": {"error_messages": {"required": "Le prénom est obligatoire."}},
            "last_name":  {"error_messages": {"required": "Le nom est obligatoire."}},
            "role":       {"error_messages": {"required": "Le rôle est obligatoire."}},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.schools.models import School
        self.fields["school"] = serializers.PrimaryKeyRelatedField(
            queryset=School.objects.all(),
            required=False,
            allow_null=True,
            error_messages={
                "does_not_exist": "Établissement introuvable.",
                "incorrect_type": "Identifiant d'établissement invalide.",
            },
        )

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError(
                "Cette adresse email est déjà utilisée."
            )
        return value.lower()

    def validate_role(self, value):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return value
        requester = request.user
        if requester.is_admin() and value not in ADMIN_ALLOWED_ROLES:
            raise serializers.ValidationError(
                "En tant qu'administrateur, vous pouvez créer uniquement "
                "des enseignants, parents ou élèves."
            )
        return value

    def validate(self, attrs):
        # 1. Mots de passe
        pwd  = attrs.get("password",  "")
        pwd2 = attrs.get("password2", "")
        if pwd != pwd2:
            raise serializers.ValidationError(
                {"password2": "Les mots de passe ne correspondent pas."}
            )

        request  = self.context.get("request")
        role     = attrs.get("role", "student")

        if request and request.user.is_authenticated:
            requester = request.user

            # 2. Isolation tenant
            if requester.is_admin():
                # Un admin crée TOUJOURS dans son établissement, même si le
                # frontend envoie un school_id différent (ou aucun).
                attrs["school"] = requester.school
            elif requester.is_superadmin() and role != "superadmin":
                if not attrs.get("school"):
                    raise serializers.ValidationError(
                        {"school": "Un établissement est requis pour ce rôle."}
                    )

        # 3. Contrainte globale
        if role != "superadmin" and not attrs.get("school"):
            raise serializers.ValidationError(
                {"school": "Un établissement est requis pour créer cet utilisateur."}
            )

        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        email    = validated_data["email"]
        # Auto-génération du username unique côté backend
        validated_data["username"] = generate_unique_username(email)
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        logger.info("Compte créé : %s (role=%s)", user.email, user.role)
        return user


# ── Changement de mot de passe ─────────────────────────────────────────────────

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        required=True,
        error_messages={"required": "L'ancien mot de passe est obligatoire."},
    )
    new_password = serializers.CharField(
        required=True,
        validators=[validate_password],
        error_messages={"required": "Le nouveau mot de passe est obligatoire."},
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                "L'ancien mot de passe est incorrect."
            )
        return value


# ── Réinitialisation par un administrateur (P2 v4) ────────────────────────────

class AdminResetPasswordSerializer(serializers.Serializer):
    """
    Saisie du nouveau mot de passe temporaire par un admin/superadmin
    (solution A du cahier des charges). La cible est passée via le contexte
    pour que les validateurs Django (similarité avec les attributs de
    l'utilisateur, etc.) s'appliquent à la CIBLE, pas à l'auteur.
    """
    new_password = serializers.CharField(
        required=True, write_only=True,
        error_messages={"required": "Le nouveau mot de passe est obligatoire."},
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True,
        error_messages={"required": "La confirmation du mot de passe est obligatoire."},
    )

    def validate_new_password(self, value):
        validate_password(value, user=self.context.get("target_user"))
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Les mots de passe ne correspondent pas."}
            )
        return attrs


# ── JWT Login ───────────────────────────────────────────────────────────────────

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login par email + mot de passe. Embarque les claims tenant dans le JWT."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"]        = user.role
        token["school_id"]   = user.school_id
        token["school_slug"] = user.school.slug if user.school_id else None
        return token

    def validate(self, attrs):
        email    = attrs.get("email", "").strip()
        password = attrs.get("password", "")

        if not email:
            raise serializers.ValidationError({"email": "L'email est obligatoire."})
        if not password:
            raise serializers.ValidationError({"password": "Le mot de passe est obligatoire."})

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )
        if not user:
            raise serializers.ValidationError(
                "Identifiants incorrects. Vérifiez votre email et votre mot de passe."
            )
        if not user.is_active:
            raise serializers.ValidationError(
                "Ce compte est désactivé. Contactez votre administrateur."
            )

        if not user.is_superadmin():
            self._validate_tenant(user)

        if user.role in ("student", "parent"):
            self._check_role_specific(user)

        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access":  str(refresh.access_token),
            # Le frontend force le parcours « nouveau mot de passe obligatoire »
            # quand un administrateur a réinitialisé le compte.
            "must_change_password": user.must_change_password,
        }

    def _validate_tenant(self, user):
        if user.school_id is None:
            raise serializers.ValidationError(
                "Votre compte n'est rattaché à aucun établissement. "
                "Contactez votre administrateur."
            )
        if not user.school.is_active:
            raise serializers.ValidationError(
                "Cet établissement est actuellement désactivé. "
                "Contactez le support."
            )

    def _check_role_specific(self, user):
        from apps.schools.models import SchoolYear

        active_year = SchoolYear.objects.filter(
            school=user.school, is_current=True,
        ).first()
        if not active_year:
            return

        if user.role == "student":
            try:
                student = user.student_profile
                if not student.is_active:
                    raise serializers.ValidationError(
                        "Votre compte élève est désactivé pour cette année scolaire."
                    )
            except serializers.ValidationError:
                raise
            except Exception as exc:
                logger.warning(
                    "Profil élève absent pour user %s lors du login : %s",
                    user.email, exc,
                )
        elif user.role == "parent":
            try:
                user.parent_profile.children_links.filter(
                    student__is_active=True,
                ).exists()
            except Exception as exc:
                logger.warning(
                    "Profil parent absent pour user %s lors du login : %s",
                    user.email, exc,
                )
