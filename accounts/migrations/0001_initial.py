from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FileRef',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='uploads/')),
            ],
        ),
        migrations.CreateModel(
            name='SeedsForAI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan_seed', models.TextField()),
                ('quiz_seed', models.TextField()),
                ('fsrs_seed', models.TextField()),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='seeds', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserContext',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('persona', models.CharField(max_length=20)),
                ('goal', models.CharField(max_length=100)),
                ('deadline', models.DateField()),
                ('weekly_time_hours', models.IntegerField()),
                ('study_routine', models.TextField()),
                ('background_level', models.CharField(max_length=100)),
                ('background_institution_type', models.CharField(max_length=20)),
                ('self_assessment', models.JSONField(default=dict)),
                ('diagnostic_status', models.CharField(max_length=20)),
                ('diagnostic_snapshot', models.JSONField(default=list)),
                ('interests', models.JSONField(default=list)),
                ('preferences_formats', models.JSONField(default=list)),
                ('preferences_language', models.CharField(max_length=50)),
                ('preferences_accessibility', models.JSONField(default=list)),
                ('tech_device', models.CharField(max_length=100)),
                ('tech_connectivity', models.CharField(max_length=100)),
                ('notifications', models.CharField(max_length=100)),
                ('consent_lgpd', models.BooleanField(default=False)),
                ('materials', models.ManyToManyField(blank=True, related_name='user_contexts', to='accounts.fileref')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='context', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TeacherContext',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subjects', models.JSONField(default=list)),
                ('grades', models.JSONField(default=list)),
                ('curricular_alignment', models.TextField()),
                ('classes', models.TextField()),
                ('assessment_prefs', models.TextField()),
                ('goals', models.JSONField(default=list)),
                ('calendar', models.TextField()),
                ('integrations', models.JSONField(default=list)),
                ('consent_lgpd', models.BooleanField(default=False)),
                ('materials', models.ManyToManyField(blank=True, related_name='teacher_contexts', to='accounts.fileref')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_context', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='seedsforai',
            name='rag_corpus',
            field=models.ManyToManyField(blank=True, related_name='seed_sets', to='accounts.fileref'),
        ),
    ]
