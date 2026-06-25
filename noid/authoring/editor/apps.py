from django.apps import AppConfig


class EditorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'editor'

    def ready(self):
        from .catalog import load_collections
        load_collections()
