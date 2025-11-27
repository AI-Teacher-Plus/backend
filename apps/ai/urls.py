from django.urls import path
from .views import (
    IndexDocumentView,
    SearchView,
    ChatView,
    ChatSSEView,
    StudyPlanListView,
    GenerateStudyPlanView,
    StudyPlanDetailView,
    GenerateSectionTasksView,
    GenerateStudyDayView,
    StudyPlanMaterialUploadView,
    JobStatusView,
    JobStreamView,
)

urlpatterns = [
    path("index/", IndexDocumentView.as_view()),
    path("search/", SearchView.as_view()),
    path('chat/', ChatView.as_view(), name='ai_chat'),
    path('chat/stream/', ChatSSEView.as_view(), name='ai_chat_stream'),
    path("study-plans/", StudyPlanListView.as_view(), name="study_plan_list"),
    path("study-plans/generate/", GenerateStudyPlanView.as_view(), name="generate_study_plan"),
    path("study-plans/<uuid:plan_id>/", StudyPlanDetailView.as_view(), name="study_plan_detail"),
    path("study-plans/<uuid:plan_id>/days/<uuid:day_id>/generate/", GenerateStudyDayView.as_view(), name="study_plan_day_generate"),
    path("study-plans/<uuid:plan_id>/tasks/", GenerateSectionTasksView.as_view(), name="study_plan_tasks"),
    path("study-plans/<uuid:plan_id>/materials/", StudyPlanMaterialUploadView.as_view(), name="study_plan_material"),
    path("jobs/<str:job_id>/", JobStatusView.as_view(), name="job_status"),
    path("jobs/stream/", JobStreamView.as_view(), name="job_stream"),
]
