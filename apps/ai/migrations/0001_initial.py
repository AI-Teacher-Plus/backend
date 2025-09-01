from django.db import migrations, models
import django.db.models.deletion
from pgvector.django import VectorExtension, VectorField, HnswIndex


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        VectorExtension(),  # cria EXTENSION vector
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.UUIDField(primary_key=True, editable=False)),
                ("title", models.CharField(max_length=255)),
                ("source", models.CharField(max_length=50, default="upload")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Chunk",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("order", models.IntegerField(default=0)),
                ("text", models.TextField()),
                ("embedding", VectorField(dimensions=1536, null=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="ai.document",
                    ),
                ),
            ],
        ),
    ]
