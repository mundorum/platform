from django.contrib import admin

from .models import AuthoringSettings, Case, ContentPack, PreviewSample, Session


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'revision', 'published_revision', 'updated_at')
    search_fields = ('title', 'owner__email')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(ContentPack)
class ContentPackAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'is_active', 'loaded_at')
    list_filter = ('is_active',)
    # Packs are loaded with `manage.py load_vp_content`, which validates
    # them; editing the JSON here would bypass that.
    readonly_fields = ('name', 'source', 'data', 'loaded_at')

    def has_add_permission(self, request):
        return False


@admin.register(PreviewSample)
class PreviewSampleAdmin(admin.ModelAdmin):
    list_display = ('key', 'kind', 'created_at')
    list_filter = ('kind',)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('case', 'user', 'mode', 'revision', 'finished', 'updated_at')
    list_filter = ('mode', 'finished')
    search_fields = ('case__title', 'user__email')
    readonly_fields = ('id', 'case', 'user', 'mode', 'revision', 'document', 'state', 'created_at', 'updated_at')


@admin.register(AuthoringSettings)
class AuthoringSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'updated_by', 'updated_at')
    # Edited in the Authoring Assistant's settings panel, which validates
    # them against the pack; deleting one here resets it.
    readonly_fields = ('user', 'data', 'updated_by', 'updated_at')

    def has_add_permission(self, request):
        return False
