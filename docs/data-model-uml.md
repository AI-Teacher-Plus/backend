# Modelo de dados (UML)

Panorama completo dos modelos do backend, com diagramas de classe Mermaid cobrindo contexto do usuario, plano de estudos, conteudos e ingestao/RAG.

## Contexto, plano e RAG
```mermaid
classDiagram
    class User {
        UUID id
        username
        email
    }
    class StudyContext {
        persona
        goal
        deadline
        weekly_time_hours
        preferences_*
        tech_device
        notifications
        consent_lgpd
    }
    class TeacherContext {
        subjects
        grades
        calendar
    }
    class SeedsForAI {
        plan_seed
        quiz_seed
        fsrs_seed
    }
    class StudyPlan {
        status
        generation_status
        total_days
    }
    class StudyWeek {
        week_index
        status
        start_date
        end_date
    }
    class StudyDay {
        day_index
        scheduled_date
        status
        target_minutes
        metadata
    }
    class StudyTask {
        order
        task_type
        status
        duration_minutes
        metadata
    }
    class FileRef {
        file
    }
    class Document {
        title
        source
        ingest_status
    }
    class Chunk {
        order
        text
        embedding
    }

    User "1" --> "1" StudyContext : owns
    User "1" --> "1" TeacherContext
    User "1" --> "1" SeedsForAI
    User "1" --> "*" Document : owner
    StudyContext "1" -- "0..*" FileRef : materials
    TeacherContext "1" -- "0..*" FileRef : materials
    SeedsForAI "1" -- "0..*" FileRef : rag_corpus
    StudyContext "1" --> "*" StudyPlan : study_plans
    StudyPlan "1" --> "*" StudyWeek : weeks
    StudyPlan "1" --> "*" StudyDay : days
    StudyWeek "1" --> "*" StudyDay : days
    StudyDay "1" --> "*" StudyTask : tasks
    StudyTask "*" -- "0..*" FileRef : materials
    StudyPlan "*" -- "*" Document : rag_documents
    Document "1" --> "*" Chunk : chunks
```

## Conteudo, flashcards e avaliacoes
```mermaid
classDiagram
    class StudyTask
    class LessonContent {
        summary
        body
        key_points
    }
    class ReadingContent {
        overview
        instructions
        resources
    }
    class PracticeContent {
        prompt
        expected_output
        rubric
    }
    class ProjectContent {
        brief
        deliverables
        evaluation
        resources
    }
    class ReflectionContent {
        prompt
        guidance
    }
    class ReviewSessionContent {
        topics
        strategy
        follow_up
    }
    class FlashcardSet {
        title
        description
        tags
    }
    class Flashcard {
        front
        back
        hints
        tags
    }
    class Assessment {
        assessment_type
        passing_score
        time_limit_minutes
        metadata
    }
    class AssessmentItem {
        item_type
        prompt
        choices
        answer
        difficulty
    }

    StudyTask "1" --> "0..1" LessonContent
    StudyTask "1" --> "0..1" ReadingContent
    StudyTask "1" --> "0..1" PracticeContent
    StudyTask "1" --> "0..1" ProjectContent
    StudyTask "1" --> "0..1" ReflectionContent
    StudyTask "1" --> "0..1" ReviewSessionContent
    StudyTask "1" --> "0..1" FlashcardSet
    FlashcardSet "1" --> "*" Flashcard : cards
    StudyTask "1" --> "0..1" Assessment
    Assessment "1" --> "*" AssessmentItem : items
```

## Notas por dominio
- **Identidade e contexto** (`apps/accounts/models.py`):
  - `User` usa UUID como chave primaria.
  - `StudyContext` centraliza persona, objetivo, deadline, disponibilidade, preferencias e consentimento (LGPD). Um por usuario.
  - `TeacherContext` cobre cenarios docentes; `SeedsForAI` guarda prompts-semente e corpus base (M2M com `FileRef`).
- **Plano de estudo**:
  - `StudyPlan` agrega semanas (`StudyWeek`) e dias (`StudyDay`), com estado de geracao em `generation_status` + `last_error`.
  - `StudyDay.metadata` armazena historico (`results_log`, `last_result`, `prerequisites`, `section_id`), usado pela IA em `generate_day_payload`.
  - `StudyTask` guarda ordem, tipo, duracao, materiais (M2M com `FileRef`) e `metadata.progress_log` vindo de `StudyTaskProgressView`.
- **Conteudo e avaliacao**:
  - Cada `StudyTask` pode ter um bloco 1:1 de conteudo (lesson/reading/practice/project/reflection/review) ou assessment/flashcards.
  - `Assessment` agrega `AssessmentItem` (MCQ/TF/open/short/code) e guarda metadados adicionais.
- **IA e RAG** (`apps/ai/models.py`):
  - `Document` representa material ingerido; `Chunk` guarda texto/embedding com indice HNSW para busca vetorial.
  - `StudyPlan.rag_documents` conecta materiais relevantes por plano; uploads via `PlanMaterialUploadView` tambem vinculam `FileRef` ao `StudyContext`.
- **IDs e ordenacao**:
  - Quase todas as entidades usam UUID como PK, exceto `Chunk` (auto increment) e ordem explicita em `StudyTask.order`, `StudyWeek.week_index`, `StudyDay.day_index`.

## Como ler os relacionamentos
- Setas com `"1"` e `"*"` indicam cardinalidade. `StudyTask "1" --> "0..1" LessonContent` significa um bloco opcional 1:1.
- Linhas com `--` representam M2M (ex.: `StudyPlan` <-> `Document`, `StudyTask` <-> `FileRef`).
- `metadata` em `StudyDay` e `StudyTask` funciona como extensao flexivel para logs de progresso/resultado e referencias de schema gerado pela IA.
