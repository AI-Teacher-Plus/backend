# Guia de Integração - Chat AI (Streaming com Eventos)

## Visão Geral
O endpoint de chat agora suporta dois modos: resposta única (não-streaming) e streaming via Server-Sent Events (SSE) com eventos estruturados. O streaming é usado para conversas interativas, especialmente no fluxo de onboarding onde há tool calls e geração de plano de estudos.

## Modos de Operação

### 1. Resposta Única (stream=false)
- **Endpoint**: `POST /api/ai/chat/`
- **Resposta**: JSON simples
- **Formato**:
  ```json
  {
    "reply": "Texto da resposta do assistente"
  }
  ```

### 2. Streaming SSE (stream=true)
- **Endpoint**: `POST /api/ai/chat/sse/`
- **Resposta**: Stream de eventos SSE
- **Content-Type**: `text/event-stream`

## Formato dos Eventos SSE

Cada evento tem o formato:
```
event: <tipo_evento>
data: <json_payload>
```

### Tipos de Eventos

#### `meta`
Eventos de controle da sessão:
- `session_started`: Início da sessão
- `context_committed`: Contexto do usuário persistido (após confirmação)
- `plan_generation_started`: Início da geração do plano de estudos
- `plan_generation_completed`: Plano gerado com sucesso
- `session_finished`: Fim da sessão com resumo

#### `token`
Pedação de texto gerado:
- `index`: Número sequencial do token
- `stage`: "assistant_response" ou "study_plan"
- `text`: Fragmento de texto

#### `heartbeat`
Indicador de progresso durante operações:
- `stage`: "tool_call"
- `tool`: Nome da ferramenta sendo executada

#### `error`
Erros durante o processamento:
- `stage`: Etapa onde ocorreu o erro
- `tool`: Ferramenta relacionada (se aplicável)
- `message`: Descrição do erro

## Checklist de Funcionamento

### Preparação da Requisição
- [ ] Autenticação: Usuário logado (Bearer token)
- [ ] Formato das mensagens: Array de objetos com `role` ("user"|"assistant"|"system") e `content` (string)
- [ ] `stream`: true para SSE, false para resposta única
- [ ] Exemplo payload:
  ```json
  {
    "messages": [
      {"role": "user", "content": "Olá, quero criar meu perfil"}
    ],
    "stream": true
  }
  ```

### Fluxo de Onboarding (Streaming)
- [ ] Receber `meta: session_started`
- [ ] Receber tokens com `stage: "assistant_response"` (perguntas do assistente)
- [ ] Enviar resposta do usuário (nova requisição com histórico atualizado)
- [ ] Se tool call: Receber `heartbeat` com `stage: "tool_call"`
- [ ] Após commit: Receber `meta: context_committed` com `user_context_id`
- [ ] Geração de plano: `meta: plan_generation_started`, tokens com `stage: "study_plan"`
- [ ] Fim: `meta: session_finished` com resumo (total_tokens, committed, user_context_id)

### Tratamento de Erros
- [ ] Monitorar eventos `error` com detalhes do problema
- [ ] Sessão pode terminar prematuramente com `meta: session_finished` contendo erro
- [ ] Reconectar se necessário (SSE suporta retry)

### Respostas Esperadas
- [ ] Para stream=false: JSON com campo `reply`
- [ ] Para stream=true: Sequência de eventos SSE terminando com `session_finished`
- [ ] Sempre incluir `session_id` nos logs/payloads para rastreamento
- [ ] Tokens são enviados em pedaços pequenos (chunk_size configurável via env)
- [ ] Delay entre tokens configurável via `AI_STREAM_DELAY_MS`

## Considerações Técnicas
- Conexão SSE mantém-se aberta até `session_finished`
- Tool calls são executadas automaticamente (commit_user_context para persistir contexto)
- Plano de estudos é gerado apenas após commit bem-sucedido
- Sistema prompt inclui fluxo completo de onboarding em português
- Logs detalhados disponíveis para debugging (com session_id)