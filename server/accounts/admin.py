from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile, PreAuthorization


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('role', 'google_id', 'picture_url')
    readonly_fields = ('google_id', 'picture_url')


class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(PreAuthorization)
class PreAuthorizationAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'created_at', 'notes')
    list_filter = ('role',)
    search_fields = ('email', 'notes')
    ordering = ('email',)

    def has_module_perms(self, request, app_label=None):
        return self._is_manager(request)

    def has_view_permission(self, request, obj=None):
        return self._is_manager(request)

    def has_add_permission(self, request):
        return self._is_manager(request)

    def has_change_permission(self, request, obj=None):
        return self._is_manager(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_manager(request)

    @staticmethod
    def _is_manager(request):
        if not request.user.is_active or not request.user.is_authenticated:
            return False
        try:
            return request.user.profile.role == 'manager'
        except Profile.DoesNotExist:
            # Fall back to superuser (useful for bootstrap via createsuperuser)
            return request.user.is_superuser
