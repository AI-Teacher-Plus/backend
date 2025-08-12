from django.db import models
from django.contrib.auth import get_user_model


class FileRef(models.Model):
    file = models.FileField(upload_to='uploads/')

    def __str__(self):
        return self.file.name


class UserContext(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='context')
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
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='teacher_context')
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
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='seeds')
    plan_seed = models.TextField()
    quiz_seed = models.TextField()
    fsrs_seed = models.TextField()
    rag_corpus = models.ManyToManyField(FileRef, related_name='seed_sets', blank=True)

    def __str__(self):
        return f"Seeds for {self.user}"
