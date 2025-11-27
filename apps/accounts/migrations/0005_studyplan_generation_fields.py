from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_studyplan_rag_documents"),
    ]

    operations = [
        migrations.AddField(
            model_name="studyplan",
            name="generation_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("running", "Running"), ("failed", "Failed"), ("succeeded", "Succeeded")],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="studyplan",
            name="job_id",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="studyplan",
            name="last_error",
            field=models.TextField(blank=True, default=""),
        ),
    ]
