from django.contrib import admin

from .models import Case, ContentPack, PreviewSample


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
