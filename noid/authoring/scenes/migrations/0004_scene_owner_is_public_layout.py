from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scenes', '0003_scenerun_nullable_scene_scratch_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='scene',
            name='layout',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='scene',
            name='owner',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='scenes',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='scene',
            name='is_public',
            field=models.BooleanField(default=False),
        ),
    ]
