import uuid

from django.conf import settings
from django.db import models


class Case(models.Model):
    """One virtual patient activity, authored in VP Studio.

    The whole case is one JSON document (see casedoc.py for its shape), so
    the editor can save it in one request and the format can evolve without
    a migration per field. `revision` increases on every save; publishing
    freezes a copy in `published_document`.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='vp_cases')
    title = models.CharField(max_length=300, blank=True)   # copy of document.title, for lists
    document = models.JSONField()
    revision = models.PositiveIntegerField(default=1)
    published_document = models.JSONField(null=True, blank=True)
    published_revision = models.PositiveIntegerField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f'Untitled case {self.pk}'

    @property
    def status(self) -> str:
        """'draft' (never published), 'published', or 'changed' (edited since)."""
        if self.published_revision is None:
            return 'draft'
        return 'published' if self.published_revision == self.revision else 'changed'


class ContentPack(models.Model):
    """Templates, default elements, strategies and assistant instructions.

    Loaded from a JSON file with `manage.py load_vp_content`; the most
    recently loaded active pack is used. With none loaded, the built-in
    placeholder pack (content/placeholder.json) applies.
    """
    name = models.CharField(max_length=200)
    source = models.CharField(max_length=500, blank=True)   # file name it was loaded from
    data = models.JSONField()
    is_active = models.BooleanField(default=True)
    loaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-loaded_at']

    def __str__(self):
        return f'{self.name} ({self.loaded_at:%Y-%m-%d})'


class PreviewSample(models.Model):
    """Cached LLM preview sample, keyed by a hash of everything that shapes
    it (resolved prompt, strategies, level, element kind, content pack)."""
    key = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=20)
    output = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.kind} {self.key[:10]}'
