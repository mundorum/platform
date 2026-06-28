import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('scenes', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.CharField(max_length=300)),
                ('slug_aliases', models.JSONField(default=list, help_text='Former slugs still accepted for reverse-lookup.')),
                ('extension', models.CharField(blank=True, max_length=20)),
                ('scope', models.CharField(choices=[('shared', 'Shared'), ('scene', 'Scene')], default='shared', max_length=10)),
                ('display_name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('resource_type', models.CharField(
                    choices=[('pdf', 'PDF'), ('image', 'Image'), ('csv', 'CSV'), ('python', 'Python'), ('text', 'Text'), ('other', 'Other')],
                    default='other', max_length=20,
                )),
                ('tags', models.JSONField(default=list)),
                ('mime_type', models.CharField(blank=True, max_length=100)),
                ('storage_path', models.CharField(max_length=500)),
                ('size_bytes', models.PositiveIntegerField(default=0)),
                ('sha256', models.CharField(blank=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='resources',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('scene', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='resources',
                    to='scenes.scene',
                )),
            ],
            options={
                'ordering': ['scope', 'slug'],
            },
        ),
        migrations.AddConstraint(
            model_name='resource',
            constraint=models.UniqueConstraint(
                condition=models.Q(scope='shared'),
                fields=['slug'],
                name='resource_unique_shared_slug',
            ),
        ),
        migrations.AddConstraint(
            model_name='resource',
            constraint=models.UniqueConstraint(
                condition=models.Q(scope='scene'),
                fields=['scene', 'slug'],
                name='resource_unique_scene_slug',
            ),
        ),
    ]
