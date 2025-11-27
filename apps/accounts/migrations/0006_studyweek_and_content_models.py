from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_studyplan_generation_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyWeek",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("week_index", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=200, blank=True)),
                ("focus", models.TextField(blank=True)),
                ("start_date", models.DateField(null=True, blank=True)),
                ("end_date", models.DateField(null=True, blank=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("scheduled", "Scheduled"), ("active", "Active"), ("completed", "Completed")], default="pending", max_length=20)),
                ("metadata", models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="weeks", to="accounts.studyplan")),
            ],
            options={
                "ordering": ["week_index"],
                "unique_together": {("plan", "week_index")},
            },
        ),
        migrations.AddField(
            model_name="studyday",
            name="week",
            field=models.ForeignKey(null=True, blank=True, on_delete=models.deletion.CASCADE, related_name="days", to="accounts.studyweek"),
        ),
        migrations.CreateModel(
            name="LessonContent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("summary", models.TextField(blank=True)),
                ("body", models.TextField(blank=True)),
                ("key_points", models.JSONField(default=list, blank=True)),
                ("source_refs", models.JSONField(default=list, blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="lesson_content", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="ReadingContent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("overview", models.TextField(blank=True)),
                ("instructions", models.TextField(blank=True)),
                ("resources", models.JSONField(default=list, blank=True)),
                ("generated_text", models.TextField(blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="reading_content", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="PracticeContent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("prompt", models.TextField()),
                ("expected_output", models.TextField(blank=True)),
                ("rubric", models.JSONField(default=dict, blank=True)),
                ("hints", models.JSONField(default=list, blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="practice_content", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="ProjectContent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("brief", models.TextField()),
                ("deliverables", models.JSONField(default=list, blank=True)),
                ("evaluation", models.TextField(blank=True)),
                ("resources", models.JSONField(default=list, blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="project_content", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="ReflectionContent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("prompt", models.TextField()),
                ("guidance", models.TextField(blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="reflection_content", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="ReviewSessionContent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("topics", models.JSONField(default=list, blank=True)),
                ("strategy", models.TextField(blank=True)),
                ("follow_up", models.TextField(blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="review_content", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="FlashcardSet",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("title", models.CharField(max_length=200, blank=True)),
                ("description", models.TextField(blank=True)),
                ("tags", models.JSONField(default=list, blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="flashcard_set", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="Assessment",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("assessment_type", models.CharField(choices=[("quiz", "Quiz"), ("test", "Test"), ("diagnostic", "Diagnostic"), ("practice", "Practice")], default="quiz", max_length=20)),
                ("passing_score", models.FloatField(null=True, blank=True)),
                ("time_limit_minutes", models.PositiveIntegerField(null=True, blank=True)),
                ("metadata", models.JSONField(default=dict, blank=True)),
                ("task", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="assessment", to="accounts.studytask")),
            ],
        ),
        migrations.CreateModel(
            name="Flashcard",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("front", models.TextField()),
                ("back", models.TextField()),
                ("hints", models.JSONField(default=list, blank=True)),
                ("tags", models.JSONField(default=list, blank=True)),
                ("difficulty", models.PositiveSmallIntegerField(default=1)),
                ("card_set", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="cards", to="accounts.flashcardset")),
            ],
        ),
        migrations.CreateModel(
            name="AssessmentItem",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("item_type", models.CharField(choices=[("mcq", "Multiple Choice"), ("tf", "True/False"), ("open", "Open"), ("short", "Short Answer"), ("code", "Coding")], default="mcq", max_length=20)),
                ("prompt", models.TextField()),
                ("choices", models.JSONField(default=list, blank=True)),
                ("answer", models.JSONField(default=dict, blank=True)),
                ("explanation", models.TextField(blank=True)),
                ("difficulty", models.PositiveSmallIntegerField(default=1)),
                ("metadata", models.JSONField(default=dict, blank=True)),
                ("assessment", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="items", to="accounts.assessment")),
            ],
        ),
    ]
