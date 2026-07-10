import uuid

from django.conf import settings
from django.db import models


class Resource(models.Model):
    SCOPE_SHARED = 'shared'
    SCOPE_SCENE = 'scene'
    SCOPE_CHOICES = [('shared', 'Shared'), ('scene', 'Scene')]

    TYPE_PDF      = 'pdf'
    TYPE_IMAGE    = 'image'
    TYPE_CSV      = 'csv'
    TYPE_PYTHON   = 'python'
    TYPE_TEXT     = 'text'
    TYPE_HTML_APP = 'html_app'
    TYPE_OTHER    = 'other'
    TYPE_CHOICES = [
        ('pdf',      'PDF'),
        ('image',    'Image'),
        ('csv',      'CSV'),
        ('python',   'Python'),
        ('text',     'Text'),
        ('html_app', 'HTML App'),
        ('other',    'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Address ──────────────────────────────────────────────────────────────
    # slug:      hierarchical label path chosen by the user, e.g. "datasets/census-2024"
    # extension: dot-prefixed file extension, e.g. ".csv"
    # address:   full namespace address used in scene properties: "{scope}:{slug}{ext}"
    slug        = models.CharField(max_length=300)
    slug_aliases = models.JSONField(
        default=list,
        help_text='Former slugs still accepted for reverse-lookup.',
    )
    extension   = models.CharField(max_length=20, blank=True)

    # ── Scope ─────────────────────────────────────────────────────────────────
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SCOPE_SHARED)
    scene = models.ForeignKey(
        'scenes.Scene',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='resources',
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    display_name  = models.CharField(max_length=200)
    description   = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_OTHER)
    tags          = models.JSONField(default=list)
    mime_type     = models.CharField(max_length=100, blank=True)

    # ── Physical storage ──────────────────────────────────────────────────────
    # Absolute on-disk path.  Slug-based so it's human-readable on the filesystem.
    storage_path = models.CharField(max_length=500)
    size_bytes   = models.PositiveIntegerField(default=0)
    sha256       = models.CharField(max_length=64, blank=True)

    # ── Provenance ────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, on_delete=models.SET_NULL,
        related_name='resources',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scope', 'slug']
        constraints = [
            # A slug must be unique among shared resources.
            models.UniqueConstraint(
                fields=['slug'],
                condition=models.Q(scope='shared'),
                name='resource_unique_shared_slug',
            ),
            # Within a scene, each slug must also be unique.
            models.UniqueConstraint(
                fields=['scene', 'slug'],
                condition=models.Q(scope='scene'),
                name='resource_unique_scene_slug',
            ),
        ]

    def __str__(self):
        return self.address

    @property
    def address(self) -> str:
        """Full namespace address for use in scene component properties."""
        return f'{self.scope}:{self.slug}{self.extension}'
