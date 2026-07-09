from rest_framework.permissions import BasePermission

# ── Level constants ────────────────────────────────────────────────────────────
LEVEL_SUPERADMIN = 100
LEVEL_ADMIN = 80
LEVEL_TEACHER = 50
LEVEL_PARENT = 30
LEVEL_STUDENT = 10


class IsSuperAdmin(BasePermission):
    """Only superadmins."""
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.is_superadmin())


class IsAdminOrAbove(BasePermission):
    """admin OR superadmin."""
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role_level >= LEVEL_ADMIN)


class IsTeacherOrAbove(BasePermission):
    """teacher, admin, or superadmin."""
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role_level >= LEVEL_TEACHER)


class IsAdminUser(BasePermission):
    """Strict admin (NOT superadmin via this class — use IsAdminOrAbove for both)."""
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role_level >= LEVEL_ADMIN)


class IsTeacherUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_teacher()


class IsParentUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_parent()


class IsStudentUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_student()


class IsAdminOrTeacher(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role_level >= LEVEL_TEACHER)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return request.user.is_authenticated
        return (request.user.is_authenticated and
                request.user.role_level >= LEVEL_ADMIN)


class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role_level >= LEVEL_ADMIN:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return obj == request.user


class CanManageUser(BasePermission):
    """
    Object-level: can the requester manage the target user?
    - superadmin: can manage anyone
    - admin: can manage teacher/parent/student ONLY
    - others: cannot manage any user
    """
    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role_level >= LEVEL_ADMIN)

    def has_object_permission(self, request, view, obj):
        return request.user.can_manage(obj)
