from django.contrib import admin

from .models import LLMUsage


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'provider', 'model', 'purpose',
                    'prompt_tokens', 'completion_tokens', 'latency_ms', 'ok')
    list_filter = ('provider', 'ok', 'purpose')
    search_fields = ('user__email', 'model', 'purpose')
    date_hierarchy = 'created_at'

    # An audit log: read-only in the admin.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
