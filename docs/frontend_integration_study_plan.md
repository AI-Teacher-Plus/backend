# Guia de integracao front-end: planos de estudo assincronos

## Resumo
1. Disparar geracao assincrona (plano, semanas extras, tarefas ou materiais) e guardar `job_id`.
2. Consultar o plano (ou a lista) via REST para renderizar semanas, dias e tasks tipadas.
3. Se `generation_status`/`ingest_status` estiver `pending` ou `running`, monitorar via `/jobs/{job_id}` (polling) ou `/jobs/stream/` (SSE).
4. Atualizar UI e cards assim que o job virar `succeeded` ou `failed`.

## Endpoints principais

| Acao | Metodo/rota | Request | Resposta | Observacoes |
| --- | --- | --- | --- | --- |
| Listar planos do usuario | `GET /api/ai/study-plans/` | - | `200 StudyPlanSummary[]` | Cards com status, erro e semana atual. |
| Gerar plano inicial | `POST /api/ai/study-plans/generate/` | `{ "title"?: str, "goal_override"?: str }` | `201 StudyPlanSerializer` (status `pending`, `job_id`). |
| Detalhe completo | `GET /api/ai/study-plans/{plan_id}/` | - | `200 StudyPlanSerializer` | Inclui `weeks[].days[].tasks`, `generation_status`, `rag_document_ids`. |
| Gerar tarefas para secao | `POST /api/ai/study-plans/{plan_id}/tasks/` | `{ "section_id": "s1" }` | `202 { job_id, plan_id, section_id }` | Plano volta a `pending` ate job concluir. |
| Gerar um dia especifico | `POST /api/ai/study-plans/{plan_id}/days/{day_id}/generate/` | `{ "reset_existing"?: bool }` | `202 { job_id, plan_id, day_id }` | Usa metadata do dia/`section_id` para criar ou regerar tasks daquele dia. |
| Atualizar progresso de tarefa | `POST /api/ai/study-tasks/{task_id}/progress/` | `{ "status": "pending|ready|in_progress|completed", "minutes_spent"?: int, "notes"?: str, "payload"?: {} }` | `200 { task_id, plan_id, day_id, status, day_status, metadata }` | Endpoint genérico para marcar conclusao de flashcards/quizzes/leituras/etc.; recalcula `day_status`. |
| Upload de material (RAG) | `POST /api/ai/study-plans/{plan_id}/materials/` | multipart `file`, `title?` | `202 { job_id, plan_id, file_id, document_id }`. |
| Consultar job | `GET /api/ai/jobs/{job_id}/` | - | `200 { job_id, status, result?, error? }`. |
| SSE de job | `GET /api/ai/jobs/stream/?job_id=...` | - | `text/event-stream` com eventos `meta`, `result`, `error`. |

## Estrutura de dados
- `StudyPlanSerializer` expõe:
  - `weeks[]` → cada semana tem `week_index`, status, título e `days`.
  - `weeks[].days[]` → cada dia indica `section_id`, `prerequisites`, `week_index`, `tasks`.
  - Cada dia também traz `generation_status`, `job_id`, `last_error` via `metadata` para monitorar geração incremental.
  - Cada task aceita progresso via `POST /study-tasks/{task_id}/progress/` e retorna `day_status` recalculado.
  - `days[].tasks[]` → cada task possui:
    - `task_type` (lesson, reading, practice, project, flashcards, assessment, reflection, review, etc.).
    - `content_type` (mesmo enumerado) + `content` tipado (ex.: `LessonContent`, `FlashcardSet`, `Assessment`).
    - `metadata` (refs e IDs internos), `difficulty`, `research_needed`.
  - `rag_document_ids`, `generation_status`, `last_error`, `job_id`.
- Conteudos tipados
  - `LessonContent`: summary/body/key_points/source_refs.
  - `ReadingContent`: overview/instructions/resources.
  - `PracticeContent`: prompt/expected_output/rubric/hints.
  - `ProjectContent`: brief/deliverables/evaluation/resources.
  - `ReflectionContent`, `ReviewSessionContent`.
  - `FlashcardSet` + `cards[]` (front/back/hints/difficulty).
  - `Assessment` + `items[]` (mcq/tf/open) com choices/answer/explanation.

## Fluxo recomendado

### 1) Dashboard inicial
```text
GET /api/ai/study-plans/  -> renderizar cards (titulo, status, semana atual, erro)
```
- Cards em `generation_status=pending` mostram spinner e permitem monitorar `job_id`.
- Cards com `failed` exibem `last_error` e botao de “tentar novamente”.

### 2) Criar plano
```text
POST /api/ai/study-plans/generate/
GET /api/ai/study-plans/{plan_id}/  (loop ate generation_status=succeeded)
```
- Enquanto `pending/running`: usar `GET /api/ai/jobs/{job_id}` ou SSE.
- Ao concluir, renderizar `weeks[].days[].tasks`.

### 3) Renderizacao do plano
1. Agrupar por `weeks`.
2. Para cada semana, mostrar `status` (pending/scheduled/active/completed) e `days`.
3. Em `days`, seguir `day_index` e `section_id`.
4. Para cada task, usar `content_type` e `content` tipado:
   - `lesson`/`reading`: mostrar texto/resumo e key_points.
   - `flashcards`: montar deck interativo a partir de `cards`.
   - `assessment`: criar quiz com `items`.
   - `practice`/`project`: exibir prompt, rubrica e recursos.
   - `reflection`/`review`: exibir prompts e próximos passos.

### 4) Gerar tarefas adicionais
1. `POST /study-plans/{plan_id}/tasks/ { section_id }`.
2. Plano muda para `generation_status=pending` e ganha novo `job_id`.
3. Monitorar ate `succeeded`;  entao `GET /study-plans/{plan_id}/` para ver tasks adicionadas à semana/dia correspondente.

### 5) Upload de materiais
1. `POST /study-plans/{plan_id}/materials/` (multipart).
2. Resposta traz `job_id`, `document_id`. Mostrar “processando” na UI.
3. Monitorar `GET /jobs/{job_id}` → quando `ingest_status=succeeded`, atualizar lista de materiais (via `rag_document_ids` ou endpoint dedicado).

## Polling vs SSE
- **Polling** (mais simples): chamar `GET /api/ai/jobs/{job_id}/` a cada ~5s.
- **SSE**: `GET /api/ai/jobs/stream/?job_id=...` envia:
  - `event: meta` `{ job_id, status }` sempre que muda.
  - `event: result` com payload final (ex.: plan_id, tasks, document_id).
  - `event: error` quando a task falha.

## Tratamento de erros
- `generation_status = "failed"` → usar `last_error` para mensagem e permitir reprocessar (novo POST).
- `Document.ingest_status = "failed"` → mostrar erro e permitir reupload.
- Endpoint `/jobs/{job_id}` tambem retorna `error` se a task falhar antes do modelo refletir.

## Sequencia resumida
1. Dashboard: `GET /study-plans/`.
2. Criar plano: `POST /study-plans/generate/` → monitorar job → `GET /study-plans/{id}/`.
3. Consumir plano: renderizar semanas/dias/tasks com `content_type`.
4. Gerar novas tarefas conforme progresso (`POST /study-plans/{id}/tasks/`).
5. Enriquecer com materiais (`POST /study-plans/{id}/materials/`).
6. Sempre monitorar jobs via `/jobs/{job_id}` ou SSE e atualizar UI conforme status muda.

Com esse fluxo o front tem visibilidade total sobre planos, semanas, conteudos tipados e eventos assincronos, sem depender de estados locais.
