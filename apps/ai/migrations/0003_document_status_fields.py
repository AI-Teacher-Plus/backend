from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0002_document_owner_alter_document_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="ingest_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("running", "Running"), ("failed", "Failed"), ("succeeded", "Succeeded")],
                default="succeeded",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="job_id",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="last_error",
            field=models.TextField(blank=True, default=""),
        ),
    ]
