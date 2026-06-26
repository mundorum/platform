from django.db import models


class ComponentCollection(models.Model):
    """A pip-installed Python package that registers one or more Noid components."""

    name = models.CharField(max_length=120, unique=True)
    pip_package = models.CharField(
        max_length=200, blank=True,
        help_text="pip install target, e.g. 'mundorum-noid-collections[lm]'",
    )
    modules = models.JSONField(
        default=list,
        help_text="Importable module paths that register Noid components.",
    )
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
