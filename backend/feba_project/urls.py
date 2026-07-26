from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/schools/', include('apps.schools.urls')),
    path('api/classes/', include('apps.classes.urls')),
    path('api/students/', include('apps.students.urls')),
    path('api/teachers/', include('apps.teachers.urls')),
    path('api/parents/', include('apps.parents.urls')),
    path('api/subjects/', include('apps.subjects.urls')),
    path('api/grades/', include('apps.grades.urls')),
    path('api/bulletins/', include('apps.bulletins.urls')),
    path('api/attendance/', include('apps.attendance.urls')),
    path('api/schedule/', include('apps.schedule.urls')),
    path('api/homework/', include('apps.homework.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/messages/', include('apps.messaging.urls')),
    path('api/announcements/', include('apps.announcements.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/user-files/', include('apps.user_files.urls')),
    path('api/dashboard/', include('apps.dashboard.urls')),
    path('api/virtual-rooms/', include('apps.virtualclass.urls')),
    path('api/health/', include('apps.dashboard.health_urls')),
    path('api/website/', include('apps.website.urls')),
    path('api/incidents/', include('apps.incidents.urls')),
    path('api/', include('apps.core.urls')),  # plateforme SaaS (superadmin)
]

if settings.DEBUG:
    # debug_toolbar n'est présent que dans certains environnements de dev :
    # ne l'importer que s'il est réellement installé (sinon DEBUG=True sans
    # le paquet faisait planter TOUT le routage au démarrage).
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
