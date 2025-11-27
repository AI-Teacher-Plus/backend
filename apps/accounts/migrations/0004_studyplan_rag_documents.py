from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0002_document_owner_alter_document_id_and_more"),
        ("accounts", "0003_alter_usercontext_background_level_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="studyplan",
            name="rag_documents",
            field=models.ManyToManyField(blank=True, related_name="study_plans", to="ai.document"),
        ),
    ]
