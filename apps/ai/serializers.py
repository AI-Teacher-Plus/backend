from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import StudyPlan, StudyTask, StudyDay
from apps.ai.models import Document


class DocumentIngestSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=255)
    text = serializers.CharField()


class DocumentIngestResponseSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    chunks = serializers.IntegerField()


class SearchResultSerializer(serializers.Serializer):
    text = serializers.CharField()
    score = serializers.FloatField()


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant", "system"])
    content = serializers.CharField()


class ChatRequestSerializer(serializers.Serializer):
    messages = ChatMessageSerializer(many=True)
    stream = serializers.BooleanField(required=False, default=False)


class ChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()


class GeneratePlanRequestSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    goal_override = serializers.CharField(required=False, allow_blank=True)


class GenerateTasksRequestSerializer(serializers.Serializer):
    section_id = serializers.CharField()


class TaskProgressRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "ready", "in_progress", "completed"])
    minutes_spent = serializers.IntegerField(required=False, min_value=0, default=0)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    payload = serializers.DictField(required=False, allow_empty=True)

    def validate_payload(self, value):
        return value or {}


class GenerateDayRequestSerializer(serializers.Serializer):
    reset_existing = serializers.BooleanField(required=False, default=True)


class PlanMaterialUploadSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField()


class PlanMaterialUploadResponseSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    chunks = serializers.IntegerField()
    file_id = serializers.UUIDField()


class LessonContentSerializer(serializers.Serializer):
    summary = serializers.CharField()
    body = serializers.CharField()
    key_points = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    source_refs = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    def to_representation(self, obj):
        return {
            "summary": obj.summary or "",
            "body": obj.body or "",
            "key_points": obj.key_points or [],
            "source_refs": obj.source_refs or [],
        }


class ReadingContentSerializer(serializers.Serializer):
    overview = serializers.CharField()
    instructions = serializers.CharField()
    resources = serializers.ListField(child=serializers.DictField(), allow_empty=True)
    generated_text = serializers.CharField()

    def to_representation(self, obj):
        return {
            "overview": obj.overview or "",
            "instructions": obj.instructions or "",
            "resources": obj.resources or [],
            "generated_text": obj.generated_text or "",
        }


class PracticeContentSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    expected_output = serializers.CharField(allow_blank=True)
    rubric = serializers.DictField()
    hints = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    def to_representation(self, obj):
        return {
            "prompt": obj.prompt or "",
            "expected_output": obj.expected_output or "",
            "rubric": obj.rubric or {},
            "hints": obj.hints or [],
        }


class ProjectContentSerializer(serializers.Serializer):
    brief = serializers.CharField()
    deliverables = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    evaluation = serializers.CharField(allow_blank=True)
    resources = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    def to_representation(self, obj):
        return {
            "brief": obj.brief or "",
            "deliverables": obj.deliverables or [],
            "evaluation": obj.evaluation or "",
            "resources": obj.resources or [],
        }


class ReflectionContentSerializer(serializers.Serializer):
    prompt = serializers.CharField()
    guidance = serializers.CharField(allow_blank=True)

    def to_representation(self, obj):
        return {"prompt": obj.prompt or "", "guidance": obj.guidance or ""}


class ReviewSessionContentSerializer(serializers.Serializer):
    topics = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    strategy = serializers.CharField(allow_blank=True)
    follow_up = serializers.CharField(allow_blank=True)

    def to_representation(self, obj):
        return {
            "topics": obj.topics or [],
            "strategy": obj.strategy or "",
            "follow_up": obj.follow_up or "",
        }


class FlashcardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    front = serializers.CharField()
    back = serializers.CharField()
    hints = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    tags = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    difficulty = serializers.IntegerField()

    def to_representation(self, obj):
        return {
            "id": obj.id,
            "front": obj.front,
            "back": obj.back,
            "hints": obj.hints or [],
            "tags": obj.tags or [],
            "difficulty": obj.difficulty or 1,
        }


class FlashcardSetSerializer(serializers.Serializer):
    title = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    cards = FlashcardSerializer(many=True, source="cards.all")

    def to_representation(self, obj):
        return {
            "title": obj.title or "",
            "description": obj.description or "",
            "tags": obj.tags or [],
            "cards": FlashcardSerializer(obj.cards.all(), many=True).data,
        }


class AssessmentItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    item_type = serializers.CharField()
    prompt = serializers.CharField()
    choices = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    answer = serializers.DictField()
    explanation = serializers.CharField(allow_blank=True)
    difficulty = serializers.IntegerField()
    metadata = serializers.DictField()

    def to_representation(self, obj):
        return {
            "id": obj.id,
            "item_type": obj.item_type,
            "prompt": obj.prompt,
            "choices": obj.choices or [],
            "answer": obj.answer or {},
            "explanation": obj.explanation or "",
            "difficulty": obj.difficulty or 1,
            "metadata": obj.metadata or {},
        }


class AssessmentSerializer(serializers.Serializer):
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    assessment_type = serializers.CharField()
    passing_score = serializers.FloatField(allow_null=True)
    time_limit_minutes = serializers.IntegerField(allow_null=True)
    metadata = serializers.DictField()
    items = AssessmentItemSerializer(many=True, source="items.all")

    def to_representation(self, obj):
        return {
            "title": obj.title,
            "description": obj.description or "",
            "assessment_type": obj.assessment_type,
            "passing_score": obj.passing_score,
            "time_limit_minutes": obj.time_limit_minutes,
            "metadata": obj.metadata or {},
            "items": AssessmentItemSerializer(obj.items.all(), many=True).data,
        }


class StudyTaskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    day = serializers.UUIDField(source="day_id")
    order = serializers.IntegerField()
    task_type = serializers.CharField()
    status = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    duration_minutes = serializers.IntegerField()
    resources = serializers.ListField(child=serializers.DictField(), allow_empty=True)
    section_id = serializers.SerializerMethodField()
    difficulty = serializers.SerializerMethodField()
    research_needed = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    metadata = serializers.DictField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_section_id(self, obj: StudyTask):
        return (obj.metadata or {}).get("section_id")

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_difficulty(self, obj: StudyTask):
        return (obj.metadata or {}).get("difficulty")

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_research_needed(self, obj: StudyTask):
        return (obj.metadata or {}).get("research_needed")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_content_type(self, obj: StudyTask):
        if hasattr(obj, "lesson_content"):
            return "lesson"
        if hasattr(obj, "reading_content"):
            return "reading"
        if hasattr(obj, "practice_content"):
            return "practice"
        if hasattr(obj, "project_content"):
            return "project"
        if hasattr(obj, "reflection_content"):
            return "reflection"
        if hasattr(obj, "review_content"):
            return "review"
        if hasattr(obj, "flashcard_set"):
            return "flashcards"
        if hasattr(obj, "assessment"):
            return "assessment"
        return None

    @extend_schema_field(serializers.DictField())
    def get_content(self, obj: StudyTask):
        if hasattr(obj, "lesson_content"):
            return LessonContentSerializer(obj.lesson_content).data
        if hasattr(obj, "reading_content"):
            return ReadingContentSerializer(obj.reading_content).data
        if hasattr(obj, "practice_content"):
            return PracticeContentSerializer(obj.practice_content).data
        if hasattr(obj, "project_content"):
            return ProjectContentSerializer(obj.project_content).data
        if hasattr(obj, "reflection_content"):
            return ReflectionContentSerializer(obj.reflection_content).data
        if hasattr(obj, "review_content"):
            return ReviewSessionContentSerializer(obj.review_content).data
        if hasattr(obj, "flashcard_set"):
            return FlashcardSetSerializer(obj.flashcard_set).data
        if hasattr(obj, "assessment"):
            return AssessmentSerializer(obj.assessment).data
        return (obj.metadata or {}).get("content", {})


class StudyDaySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    day_index = serializers.IntegerField()
    scheduled_date = serializers.DateField(allow_null=True)
    title = serializers.CharField(allow_blank=True)
    focus = serializers.CharField(allow_blank=True)
    target_minutes = serializers.IntegerField()
    status = serializers.CharField()
    section_id = serializers.SerializerMethodField()
    prerequisites = serializers.SerializerMethodField()
    week_index = serializers.SerializerMethodField()
    tasks = StudyTaskSerializer(many=True, source="tasks.all")
    metadata = serializers.DictField()
    generation_status = serializers.SerializerMethodField()
    job_id = serializers.SerializerMethodField()
    last_error = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_section_id(self, obj):
        return (obj.metadata or {}).get("section_id")

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_prerequisites(self, obj):
        return (obj.metadata or {}).get("prerequisites", [])

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_week_index(self, obj):
        week = getattr(obj, "week", None)
        return week.week_index if week else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_generation_status(self, obj):
        return (obj.metadata or {}).get("generation_status")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_job_id(self, obj):
        return (obj.metadata or {}).get("job_id")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_last_error(self, obj):
        return (obj.metadata or {}).get("last_error")


class StudyWeekSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    week_index = serializers.IntegerField()
    title = serializers.CharField(allow_blank=True)
    focus = serializers.CharField(allow_blank=True)
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    status = serializers.CharField()
    metadata = serializers.DictField()
    days = StudyDaySerializer(many=True, source="days.all")


class StudyPlanSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField(allow_blank=True)
    summary = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    total_days = serializers.IntegerField()
    metadata = serializers.DictField()
    weeks = StudyWeekSerializer(many=True, source="weeks.all")
    days = StudyDaySerializer(many=True, source="days.all")
    rag_document_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
        source="rag_documents",
    )
    generation_status = serializers.CharField()
    last_error = serializers.CharField(allow_blank=True)
    job_id = serializers.CharField(allow_blank=True, allow_null=True)



class StudyPlanSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    generation_status = serializers.CharField()
    last_error = serializers.CharField(allow_blank=True)
    job_id = serializers.CharField(allow_blank=True, allow_null=True)
    summary = serializers.CharField(allow_blank=True)
    total_days = serializers.IntegerField()
    current_week = serializers.CharField(read_only=True)
    generated_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def to_representation(self, instance: StudyPlan):
        data = super().to_representation(instance)
        week = instance.weeks.order_by("week_index").first()
        if week:
            title = week.title or f"Week {week.week_index}"
            data["current_week"] = f"{title} ({week.status})"
        else:
            data["current_week"] = ""
        return data


class StudyPlanWeekOverviewSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    weeks = StudyWeekSerializer(many=True)


class CreateStudyDayRequestSerializer(serializers.Serializer):
    week_id = serializers.UUIDField(required=False, allow_null=True)
    scheduled_date = serializers.DateField(required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True)
    focus = serializers.CharField(required=False, allow_blank=True)
    target_minutes = serializers.IntegerField(required=False, min_value=0)
    goal_override = serializers.CharField(required=False, allow_blank=True)
    context_snapshot = serializers.DictField(required=False)
    metadata = serializers.DictField(required=False)
    auto_generate = serializers.BooleanField(required=False, default=True)
    reset_existing = serializers.BooleanField(required=False, default=True)


class CreateStudyDayResponseSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    job_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    day = serializers.DictField()


class StudyDayResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[choice[0] for choice in StudyDay.STATUS_CHOICES],
        required=False,
    )
    minutes_spent = serializers.IntegerField(required=False, min_value=0)
    score = serializers.FloatField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    payload = serializers.DictField(required=False)


class JobStatusSerializer(serializers.Serializer):
    job_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.DictField(required=False, allow_null=True)
    error = serializers.CharField(required=False, allow_blank=True)
