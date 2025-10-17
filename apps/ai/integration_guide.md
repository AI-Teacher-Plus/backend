---
title: Guia de Integração — Chat AI (SSE)
---

# Visão Geral

O backend expõe dois modos para conversar com o assistente:

- **Resposta única** (`POST /api/ai/chat/`): obtém todo o texto de uma vez.
- **Streaming SSE** (`POST /api/ai/chat/sse/`): envia fragmentos e eventos estruturados em tempo real, possibilitando tool calls, persistência do `UserContext` e geração do plano de estudos.

Este guia foca no fluxo SSE e descreve todos os eventos que o front-end deve tratar.

# Payload de Requisição

```json
{
  "messages": [
    {"role": "user", "content": "Quero criar meu perfil"}
  ],
  "stream": true
}
```

- `role`: `user`, `assistant` ou `system`.
- Cada requisição precisa incluir o histórico anterior (conversação stateless).
- Autenticação obrigatória via Bearer Token.

# Envelope SSE

Cada mensagem segue o formato padrão do protocolo:

```
event: <nome_do_evento>
data: <json>
```

O backend envia `retry: 1000` no início para orientar o client a tentar reconectar em caso de queda.

# Eventos Disponíveis

## `meta`

Eventos de controle. O campo `data.type` identifica o estágio.

| type                       | Significado                                                                                                  | Payload (campos adicionais)                                      |
|---------------------------|---------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| `session_started`         | Conexão iniciada e prompt preparado.                                                                          | `session_id`                                                     |
| `context_committed`       | Tool `commit_user_context` executou com sucesso.                                                              | `session_id`, `user_context_id`                                  |
| `plan_generation_started` | LLM começou a streamar o plano de estudos.                                                                    | `session_id`, `user_context_id`                                  |
| `plan_generation_completed` | Stream do plano concluiu sem erro.                                                                           | `session_id`, `user_context_id`, `tokens_streamed`               |
| `session_finished`        | Sessão encerrada. Verifique `committed` e `error`.                                                            | `session_id`, `total_tokens`, `committed`, `user_context_id`, `error?` |

### Recomendações de UI

- Use `session_started` para inicializar o estado local e vincular `session_id`.
- `context_committed` deve disparar feedback visual (“contexto salvo”) e habilitar transições para dashboards ou loaders.
- Ao receber `plan_generation_started`, mostre indicador de carregamento e prepare a área de exibição do plano.
- `plan_generation_completed` confirma que todo o texto foi recebido; renderize ou salve o plano.
- `session_finished` encerra a stream. Se `error` estiver presente, mostre mensagem e permita recomeçar.

## `token`

Fragmentos de texto.

```json
{
  "index": 12,
  "stage": "study_plan",
  "text": "Dia 1 — Fundamentos Java..."
}
```

- `stage` pode ser:
  - `assistant_response`: conversa durante a coleta de dados.
  - `study_plan`: geração do plano após o commit.
- Recomenda-se concatenar mantendo a ordem por `index`.

## `heartbeat`

Mantém a conexão viva durante operações demoradas (ex.: execução da tool).

```json
{
  "stage": "tool_call",
  "tool": "commit_user_context"
}
```

- Útil para mostrar status (“salvando informações…”).

## `error`

Erros estruturados.

```json
{
  "stage": "tool_call",
  "tool": "commit_user_context",
  "message": "UserContextSerializer validation error"
}
```

- Sempre seguido por `meta` com `session_finished`. Use o payload para mensagens ao usuário.

# Checklist de Integração

- [ ] Abrir conexão SSE e registrar listener para todos os eventos acima.
- [ ] Armazenar `session_id` recebido em `meta`.
- [ ] Manter buffer dos `token` por `stage`.
- [ ] Tratar `context_committed` para atualizar o app state (contexto salvo).
- [ ] Tratar `plan_generation_*` para iniciar/parar loaders de plano.
- [ ] Encerrar UI ao receber `session_finished` (sucesso ou erro).
- [ ] Realizar reconexão ou fallback se a stream encerrar sem `session_finished`.

# Boas Práticas de Front-end

- **Backlog do Chat**: renderize mensagens conforme os tokens chegam.
- **Estado “Salvando”**: quando chegar `heartbeat` + `tool_call`, mostre progresso até `context_committed`.
- **Plano de Estudos**: concatene tokens de `stage: study_plan` em um buffer separado para exibição e persistência local.
- **Erros**: em `error`, logue o `session_id` e ofereça opção de tentar novamente.
- **Retentativas**: respeite cabeçalho `retry` se precisar reconectar.

# Fluxo Comentado

1. Front envia histórico com `stream: true`.
2. Recebe `meta` → `session_started`.
3. Recebe vários `token` (`assistant_response`) com as perguntas do Wizard.
4. Usuário responde; front reenvia histórico atualizado.
5. LLM chama tool → backend emite `heartbeat` (tool call) e, ao concluir, `meta` → `context_committed`.
6. Backend dispara `plan_generation_started` e tokens (`study_plan`).
7. Finaliza com `plan_generation_completed` e `session_finished`.

# Logs e Observabilidade

- Cada evento inclui `session_id` para rastrear no backend.
- Logs adicionais:
  - `tool_call_result`: tool executada com chaves do retorno.
  - `response_content_fallback`: modelo sem content; fallback em texto.
  - `model_content_skipped` / `plan_history_without_model_content`: úteis para debug.

# Próximos Passos (Roadmap)

- Integrar GET `/user-context/` para pré-carregar estados.
- Implementar fluxo de avaliação diagnóstica (modelo `DiagnosticAssessment`).
- Persistir planos via `StudyPlan`, `StudyDay`, `StudyTask` e expor endpoints REST para leitura.

Este guia será atualizado à medida que novos eventos ou ferramentas forem adicionados.
