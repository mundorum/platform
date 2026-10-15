from django.apps import AppConfig


class VpStudioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vp_studio'
    # Short label: tables are vp_<model> in the shared database.
    label = 'vp'
    verbose_name = 'VP Studio'
