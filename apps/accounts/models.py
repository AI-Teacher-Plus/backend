import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class FileRef(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='uploads/')

    def __str__(self):
        return self.file.name


class UserContext(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='context')
    persona = models.CharField(max_length=20)
    goal = models.CharField(max_length=100)
    deadline = models.DateField()
    weekly_time_hours = models.IntegerField()
    study_routine = models.TextField()
    background_level = models.CharField(max_length=2000)
    self_assessment = models.JSONField(default=dict, null=True)
    diagnostic_status = models.CharField(max_length=20, null=True, blank=True)
    diagnostic_snapshot = models.JSONField(default=list, null=True)
    interests = models.JSONField(default=list)
    materials = models.ManyToManyField(FileRef, related_name='user_contexts', blank=True)
    preferences_formats = models.JSONField(default=list)
    preferences_language = models.CharField(max_length=50)
    preferences_accessibility = models.JSONField(default=list)
    tech_device = models.CharField(max_length=100)
    tech_connectivity = models.CharField(max_length=100)
    notifications = models.CharField(max_length=100)
    consent_lgpd = models.BooleanField(default=False)

    def __str__(self):
        return f"Context for {self.user}"


class TeacherContext(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_context')
    subjects = models.JSONField(default=list)
    grades = models.JSONField(default=list)
    curricular_alignment = models.TextField()
    classes = models.TextField()
    assessment_prefs = models.TextField()
    goals = models.JSONField(default=list)
    calendar = models.TextField()
    integrations = models.JSONField(default=list)
    materials = models.ManyToManyField(FileRef, related_name='teacher_contexts', blank=True)
    consent_lgpd = models.BooleanField(default=False)

    def __str__(self):
        return f"Teacher context for {self.user}"


class SeedsForAI(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seeds')
    plan_seed = models.TextField()
    quiz_seed = models.TextField()
    fsrs_seed = models.TextField()
    rag_corpus = models.ManyToManyField(FileRef, related_name='seed_sets', blank=True)

    def __str__(self):
        return f"Seeds for {self.user}"


class StudyPlan(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_context = models.ForeignKey(UserContext, on_delete=models.CASCADE, related_name="study_plans")
    title = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    total_days = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    rag_documents = models.ManyToManyField("ai.Document", related_name="study_plans", blank=True)
    generation_status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("running", "Running"), ("failed", "Failed"), ("succeeded", "Succeeded")],
        default="pending",
    )
    last_error = models.TextField(blank=True, default="")
    job_id = models.CharField(max_length=100, null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"StudyPlan({self.user_context_id}, status={self.status})"


class StudyWeek(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("scheduled", "Scheduled"),
        ("active", "Active"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="weeks")
    week_index = models.PositiveIntegerField()
    title = models.CharField(max_length=200, blank=True)
    focus = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["week_index"]
        unique_together = ("plan", "week_index")

    def __str__(self):
        return f"StudyWeek(plan={self.plan_id}, index={self.week_index})"


class StudyDay(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ready", "Ready"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="days")
    week = models.ForeignKey(StudyWeek, on_delete=models.CASCADE, related_name="days", null=True, blank=True)
    day_index = models.PositiveIntegerField()
    scheduled_date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    focus = models.TextField(blank=True)
    target_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_index"]
        unique_together = ("plan", "day_index")

    def __str__(self):
        return f"StudyDay({self.plan_id}, index={self.day_index})"


class StudyTask(models.Model):
    TASK_TYPE_CHOICES = [
        ("lesson", "Lesson"),
        ("practice", "Practice"),
        ("review", "Review"),
        ("flashcards", "Flashcards"),
        ("assessment", "Assessment"),
        ("project", "Project"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ready", "Ready"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.ForeignKey(StudyDay, on_delete=models.CASCADE, related_name="tasks")
    order = models.PositiveIntegerField(default=1)
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, default="other")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    resources = models.JSONField(default=list, blank=True)
    materials = models.ManyToManyField(FileRef, related_name="study_tasks", blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        unique_together = ("day", "order")

    def __str__(self):
        return f"StudyTask({self.day_id}, order={self.order}, type={self.task_type})"


class LessonContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="lesson_content")
    summary = models.TextField(blank=True)
    body = models.TextField(blank=True)
    key_points = models.JSONField(default=list, blank=True)
    source_refs = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"LessonContent(task={self.task_id})"


class ReadingContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="reading_content")
    overview = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    resources = models.JSONField(default=list, blank=True)
    generated_text = models.TextField(blank=True)

    def __str__(self):
        return f"ReadingContent(task={self.task_id})"


class PracticeContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="practice_content")
    prompt = models.TextField()
    expected_output = models.TextField(blank=True)
    rubric = models.JSONField(default=dict, blank=True)
    hints = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"PracticeContent(task={self.task_id})"


class ProjectContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="project_content")
    brief = models.TextField()
    deliverables = models.JSONField(default=list, blank=True)
    evaluation = models.TextField(blank=True)
    resources = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"ProjectContent(task={self.task_id})"


class ReflectionContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="reflection_content")
    prompt = models.TextField()
    guidance = models.TextField(blank=True)

    def __str__(self):
        return f"ReflectionContent(task={self.task_id})"


class ReviewSessionContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="review_content")
    topics = models.JSONField(default=list, blank=True)
    strategy = models.TextField(blank=True)
    follow_up = models.TextField(blank=True)

    def __str__(self):
        return f"ReviewContent(task={self.task_id})"


class FlashcardSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="flashcard_set")
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"FlashcardSet(task={self.task_id})"


class Flashcard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card_set = models.ForeignKey(FlashcardSet, on_delete=models.CASCADE, related_name="cards")
    front = models.TextField()
    back = models.TextField()
    hints = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    difficulty = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"Flashcard(set={self.card_set_id})"


class Assessment(models.Model):
    ASSESSMENT_TYPES = [
        ("quiz", "Quiz"),
        ("test", "Test"),
        ("diagnostic", "Diagnostic"),
        ("practice", "Practice"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.OneToOneField(StudyTask, on_delete=models.CASCADE, related_name="assessment")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPES, default="quiz")
    passing_score = models.FloatField(null=True, blank=True)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Assessment(task={self.task_id}, type={self.assessment_type})"


class AssessmentItem(models.Model):
    ITEM_TYPES = [
        ("mcq", "Multiple Choice"),
        ("tf", "True/False"),
        ("open", "Open"),
        ("short", "Short Answer"),
        ("code", "Coding"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="items")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES, default="mcq")
    prompt = models.TextField()
    choices = models.JSONField(default=list, blank=True)
    answer = models.JSONField(default=dict, blank=True)
    explanation = models.TextField(blank=True)
    difficulty = models.PositiveSmallIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"AssessmentItem({self.assessment_id}, type={self.item_type})"
