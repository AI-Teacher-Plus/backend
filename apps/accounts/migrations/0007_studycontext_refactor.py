from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_studyweek_and_content_models"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="UserContext",
            new_name="StudyContext",
        ),
        migrations.AddField(
            model_name="studycontext",
            name="plan_label",
            field=models.CharField(blank=True, default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="studycontext",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="studycontext",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="studycontext",
            name="user",
            field=models.OneToOneField(
                on_delete=models.CASCADE,
                related_name="study_context",
                to="accounts.user",
            ),
        ),
        migrations.AlterField(
            model_name="studyplan",
            name="user_context",
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name="study_plans",
                to="accounts.studycontext",
            ),
        ),
    ]
