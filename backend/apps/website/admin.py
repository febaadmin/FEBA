"""Admin Django du site vitrine — CRUD complet du contenu public."""
from django.contrib import admin

from .models import (
    SiteSettings, HeroSlide, NewsPost, GalleryAlbum, GalleryItem,
    ContactMessage, PreRegistration,
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'phone', 'email', 'updated_at')

    def has_add_permission(self, request):
        # Singleton : une seule ligne de paramètres.
        return not SiteSettings.objects.exists()


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('order', 'title', 'is_active')
    list_editable = ('is_active',)
    ordering = ('order',)


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'is_published', 'published_at', 'event_date')
    list_filter = ('kind', 'is_published')
    search_fields = ('title', 'excerpt', 'body')
    prepopulated_fields = {}


class GalleryItemInline(admin.TabularInline):
    model = GalleryItem
    extra = 1


@admin.register(GalleryAlbum)
class GalleryAlbumAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active')
    inlines = [GalleryItemInline]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'name', 'subject', 'email', 'is_read')
    list_filter = ('is_read',)
    readonly_fields = ('name', 'email', 'phone', 'subject', 'message', 'consent', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(PreRegistration)
class PreRegistrationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'child_name', 'desired_level', 'parent_name', 'phone', 'status')
    list_filter = ('status', 'desired_level')
    readonly_fields = ('parent_name', 'phone', 'whatsapp', 'email', 'child_name',
                       'child_age', 'desired_level', 'school_year', 'message', 'created_at')

    def has_add_permission(self, request):
        return False
