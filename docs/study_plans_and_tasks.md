# Planos de Estudo e Tarefas (Assistidas por IA)

Objetivo: criar servicos que transformam um Goal em um Study Plan e em Study Tasks concretas, mantendo o UserContext extensivel e por objetivo para que cada tarefa/resultado seja reutilizado pelo modelo na proxima chamada. As respostas devem ser amigaveis para o front-end, especialmente para flashcards, quizzes/testes e recursos externos.

## Entidades centrais
- Goal: id, title, description, target_outcomes, due_date, level, interests, constraints (tempo/dia, idioma).
- StudyPlan: goal_id, sections/units (id, title, milestone, prerequisites), milestones, ai_prompt_version.
- StudyTask: plan_id, section_id, type (flashcards|quiz|lecture|summary|project|external_resource), title, description, status, difficulty (1-5), estimated_time, prerequisites, dependencies, suggested_order, context_snapshot_id.
- TaskContent (por tipo):
  - Flashcards: cards[{id, front, back, hints?, tags?, source_ref?}]
  - Quiz/Test: items[{id, type(mcq|open|tf), question, choices?, answer, explanation?, tags?, source_ref?}]
  - Lecture/Summary: {title, key_points[], summary|transcript, glossary?, source_refs?}
  - ExternalResourceSuggestion: {title, url, rationale, how_to_use, key_sections?, fallback_if_unavailable?}
- TaskResult: task_id, outcome (pass|fail|score), score?, user_notes, time_spent, artifacts (uploads/links), misconceptions?, completed_at.
- ContextSnapshot: goal_id, plan_id, section_id?, serialized_context (veja abaixo), version, created_at. Vincule cada StudyTask gerada ao snapshot usado.

## Contexto enviado para a IA (sempre incluir)
- Perfil do usuario: nivel, interesses, restricoes (tempo/dia), estilo de aprendizado, idioma.
- Goal: descricao, resultados esperados, prazo.
- Esqueleto do plano: sections/units + milestones + prerequisites.
- Progresso: tarefas recentes concluidas (id, type, section, outcome/score, misconceptions, time_spent), estatisticas agregadas, lista de misconceptions ativas.
- Perguntas abertas/bloqueios.
- Guardrails: faixa de dificuldade alvo, profundidade, requisitos de formato, max tokens.

## Fluxos de servico
1) Criar/atualizar Goal -> criar StudyPlan vazio.
2) Gerar plano:
   - Pedir a IA as secoes da ementa com prerequisites e milestones usando o contexto do usuario/goal.
   - Persistir StudyPlan; guardar ContextSnapshot com plano e prompt/resposta.
3) Gerar tarefas para uma secao/marco:
   - Prompt inclui: goal, secao, tarefas/resultados concluidos, misconceptions, orcamento de tempo, modalidade preferida, necessidade de pesquisa.
   - IA retorna tarefas com conteudo concreto; persistir StudyTask + TaskContent; guardar o context_snapshot_id em cada tarefa.
4) Executar tarefa:
   - Conteudo gerado (flashcards/quizzes/lectures) vem de TaskContent.
   - Sugestoes externas trazem rationale + passos de uso; opcionalmente disparar web/deep research para enriquecer/resumir.
5) Concluir tarefa:
   - Registrar TaskResult + notas; atualizar lista de misconceptions; criar novo ContextSnapshot com o delta.
6) Iterar:
   - Ao gerar novas tarefas, carregar o snapshot mais recente do goal/secao para adaptar dificuldade e evitar repeticao. Manter o prompt enxuto enviando as ultimas N tarefas mais agregados.

## Contrato com a IA (request/response)
- Request: pedir apenas JSON; incluir regras de formato e max de tokens.
- Schema de resposta (exemplo):
```json
{
  "plan": {
    "sections": [
      {"id": "s1", "title": "Funcoes lineares", "milestone": "Representar e interpretar graficos", "prerequisites": ["basico de algebra"]}
    ]
  },
  "tasks": [
    {
      "id": "t1",
      "section_id": "s1",
      "type": "flashcards",
      "title": "Termos-chave",
      "estimated_time": 10,
      "difficulty": 2,
      "suggested_order": 1,
      "content": {
        "cards": [
          {"id": "c1", "front": "Definicao de declive", "back": "Delta y / Delta x", "hints": ["m = rise/run"], "tags": ["declive"]}
        ]
      }
    },
    {
      "id": "t2",
      "section_id": "s1",
      "type": "quiz",
      "title": "Leitura de grafico",
      "estimated_time": 12,
      "difficulty": 3,
      "suggested_order": 2,
      "content": {
        "items": [
          {"id": "q1", "type": "mcq", "question": "Qual o declive de y=2x+1?", "choices": ["1", "2", "-2", "0"], "answer": "2", "explanation": "Coeficiente de x"}
        ]
      }
    },
    {
      "id": "t3",
      "section_id": "s1",
      "type": "external_resource",
      "title": "Video: Introducao a declive",
      "estimated_time": 15,
      "difficulty": 1,
      "suggested_order": 0,
      "research_needed": true,
      "content": {
        "url": "https://youtube.com/...",
        "rationale": "Dar intuicao visual",
        "how_to_use": "Assista de 0 a 6 min; anote exemplos de declive",
        "fallback_if_unavailable": "Pedir video alternativo"
      }
    }
  ]
}
```

Validacao:
- Rejeitar/corrigir respostas sem campos obrigatorios, com tipos incorretos ou modos nao suportados.
- Garantir ids estaveis (task/card/question) para progresso e notas no cliente.
- Respeitar limites de tokens; ao montar prompts, truncar historico para as ultimas N tarefas mais agregados.

## Web/Deep Research
- Se `research_needed` for true ou nao houver conteudo gerado, chamar web/deep research para buscar recursos.
- Persistir URLs sugeridas com rationale, secoes-chave e passos de uso; se resumir, salvar o resumo em TaskContent (lecture/summary) e linkar em source_refs.

## Notas para o front-end
- Flashcards: `front/back/hints/tags` com ids estaveis; cliente pode embaralhar/marcar facilidade.
- Quizzes: item `type`, `choices`, `answer`, `explanation` para revisao; suportar mcq/open/true-false.
- Recursos externos: url + rationale + instrucoes + fallback.
- Agendamento: `suggested_order`, `estimated_time`, `difficulty`.
- Status/progresso: TaskResult dirige conclusao, notas, misconceptions; exposto via ContextSnapshot mais recente por secao/goal.
