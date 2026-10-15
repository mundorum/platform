from django.conf import settings
from django.db import models


class LLMUsage(models.Model):
    """One gateway call. Feeds the per-user rate limit and cost tracking.

    Stores token counts and metadata only — never prompts or replies, which
    can contain student data; subprojects keep transcripts in their own models.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='llm_usage',
    )
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=200)
    # What the call was for, e.g. 'vp.assist.text' — set by the caller.
    purpose = models.CharField(max_length=80, blank=True)
    prompt_tokens = models.PositiveIntegerField(null=True, blank=True)
    completion_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'created_at'])]
        verbose_name = 'LLM usage'
        verbose_name_plural = 'LLM usage'

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.provider}/{self.model} {self.purpose}'
