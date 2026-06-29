import uuid

from django.conf import settings
from django.db import models


class Scene(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, default='Untitled Scene')
    spec = models.JSONField(default=dict)
    layout = models.JSONField(default=dict)
    package_dir = models.CharField(max_length=500, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scenes',
    )
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} ({self.id})'


class SceneRun(models.Model):
    class Status(models.TextChoices):
        PENDING     = 'pending',     'Pending'
        RUNNING     = 'running',     'Running'
        DONE        = 'done',        'Done'
        FAILED      = 'failed',      'Failed'
        INTERRUPTED = 'interrupted', 'Interrupted'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # run_id is sent to the Processing Machine so it can be addressed for cancel.
    # Stored separately from id so the PK is never exposed in the Processing API.
    run_id      = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    # scene is null for scratch runs started from the editor Play button.
    scene       = models.ForeignKey(
        Scene, on_delete=models.CASCADE,
        null=True, blank=True, related_name='runs',
    )
    # Title stored inline so scratch runs (scene=null) still have a label.
    scratch_title = models.CharField(max_length=255, blank=True, default='')
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    output      = models.TextField(blank=True)
    returncode  = models.IntegerField(null=True, blank=True)
    started_at  = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        label = self.scene_id or self.scratch_title or '(scratch)'
        return f'Run {self.id} — {label} [{self.status}]'
