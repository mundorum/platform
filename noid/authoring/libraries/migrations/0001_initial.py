from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ComponentCollection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('pip_package', models.CharField(
                    blank=True, max_length=200,
                    help_text="pip install target, e.g. 'mundorum-noid-collections[lm]'",
                )),
                ('modules', models.JSONField(
                    default=list,
                    help_text='Importable module paths that register Noid components.',
                )),
                ('enabled', models.BooleanField(default=True)),
                ('description', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
    ]
