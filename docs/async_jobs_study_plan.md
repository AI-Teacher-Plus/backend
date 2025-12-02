# Execucao Assincrona para Planos/Tarefas de Estudo e RAG

Objetivo: mover chamadas pesadas (LLM, embed, web research) para tarefas Celery, com job_id para polling, SSE para progresso e observabilidade.

## Stack
- Broker/Backend: Redis (broker) + Redis ou DB como result backend.
- Celery app: apps/ai/celery.py + settings de filas/roteamento.
- Filas: `ai_generation` (LLM), `ingest` (uploads/embeddings), `default` (misc).
- Workers: processos separados por fila; limite de concorrencia para nao saturar LLM/embedding.

## Modelos (campos novos)
- StudyPlan: generation_status (pending|running|failed|succeeded), last_error (text), job_id (char, null).
- StudyDay/StudyTask (opcional): generation_status, last_error, job_id para geracao incremental.
- Document (ou tabela auxiliar): ingest_status, last_error, job_id.
- Opcional: JobEvent(job_id, type info|error|progress, message, created_at) para SSE.

## Fluxos
1) Gerar plano:
   - POST /study-plans/generate/ -> cria StudyPlan draft com generation_status=pending e job_id, retorna o objeto completo (para UI preencher) e enfileira Celery na fila ai_generation.
   - Tarefa: generate_plan_payload + persist_plan_from_payload; marca generation_status=succeeded ou failed+last_error.
2) Gerar tarefas da secao:
   - POST /study-plans/{id}/tasks/ -> job_id; tarefa gera e persiste novas StudyTasks; atualiza status no plano/dia/secao.
3) Upload + ingest:
   - POST /study-plans/{id}/materials/ -> salva FileRef, retorna job_id; tarefa em `ingest` faz chunk+embed, cria Document/Chunk, vincula ao plano/contexto; atualiza ingest_status/last_error.
4) SSE:
   - Endpoint /api/jobs/stream/ (text/event-stream) com job_id(s). Tarefas publicam eventos (Redis pub/sub ou sinal Celery) e o backend os repassa como SSE.
5) Polling:
   - GET /api/jobs/{job_id}/ -> status/progress/last_error/result_refs.
   - Alternativa/extra: GET do recurso (StudyPlan/Document) lendo generation_status/ingest_status.

## Tarefas Celery (exemplo)
- generate_study_plan(job_id, user_id, study_context_id, goal_override, title)
- generate_section_tasks(job_id, plan_id, section_id)
- ingest_material(job_id, plan_id, file_ref_id, document_title)
- (opcional) web_research(job_id, plan_id, section_id, query)

## Eventos SSE (shape)
- meta: {job_id, status: pending|running|failed|succeeded}
- progress: {job_id, pct?, step?, message}
- result: {job_id, plan_id|task_ids|document_id}
- error: {job_id, message}

## Observabilidade
- Log estruturado (json) com job_id, queue, duracao, erro.
- Metricas: tempo por tarefa, falhas, tokens/LLM por job (se disponivel), backlog por fila.
- Health: ping Redis/Celery (tarefa de heartbeat).

## Endpoints a adaptar/criar
- POST /api/ai/study-plans/generate/ -> retorna StudyPlan (draft) com job_id, sem bloquear.
- POST /api/ai/study-plans/{id}/days/{day_id}/generate/ -> retorna job_id para criar/regenerar tasks de um dia especifico.
- POST /api/ai/study-plans/{id}/tasks/ -> retorna job_id.
- POST /api/ai/study-plans/{id}/materials/ -> retorna job_id + file_id.
- POST /api/ai/study-tasks/{task_id}/progress/ -> sincrono, marca status/tempo de uma task e recalcula status do dia.
- GET /api/ai/study-plans/{id}/ -> le generation_status/ingest_status.
- GET /api/ai/jobs/{job_id}/ -> status.
- GET or POST /api/ai/jobs/stream/?job_id=... -> SSE.

## Config/infra
- settings: CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TASK_QUEUES, CELERY_TASK_ROUTES, timeouts e retries.
- Procfile/dev: `celery -A project worker -Q ai_generation -c 2`, `celery -A project worker -Q ingest -c 2`.
- Limitar tamanho de upload; retries exponenciais para falhas transitórias; timeouts em chamadas LLM/embedding.
