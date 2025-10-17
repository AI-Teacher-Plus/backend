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
    background_level = models.CharField(max_length=100)
    background_institution_type = models.CharField(max_length=20)
    self_assessment = models.JSONField(default=dict)
    diagnostic_status = models.CharField(max_length=20)
    diagnostic_snapshot = models.JSONField(default=list)
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
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"StudyPlan({self.user_context_id}, status={self.status})"


class StudyDay(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ready", "Ready"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="days")
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
