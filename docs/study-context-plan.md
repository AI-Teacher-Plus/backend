# Plano de Evolucao do StudyContext e Geracao Dinamica de Dias

## Resumo executivo
- Criar e armazenar o plano logo apos a submissao do contexto do usuario (agora renomeado para StudyContext) para que os prompts possam usar um estado consistente.
- Reestruturar o plano para conter um "esqueleto" semanal de alto nivel persistido imediatamente e gerar dias detalhados sob demanda com base no desempenho real dos alunos.
- Assegurar que a API exponha endpoints idempotentes para carregar dinamicamente os dias e persistir resultados diarios, alimentando o ciclo de contexto futuro/presente.

## Diagnostico atual
1. O formulario de contexto e focado em um unico plano e nao coleta start_date/end_date, dificultando dados temporais e reuso.
2. O plano so e criado apos atividades subsequentes, deixando usuarios sem orientacao inicial.
3. O prompt da IA forca a geracao de todos os dias da semana de uma vez, inviabilizando ajustes dinamicos.
4. A API nao fornece mecanismo explicito para recuperar/criar dias conforme necessidade, o que bloqueia experiencias sob demanda.

## Objetivos
- Renomear StudyContext para StudyContext e permitir reutilizar as secoes gerais do formulario em multiplos planos.
- Persistir start_date/end_date e demais metadados necessarios para multiplos ciclos de estudo.
- Entregar um plano semanal de alto nivel imediato com checkpoints e criterios para liberacao de dias.
- Disponibilizar prompts e endpoints que gerem dias especificos on-demand, utilizando historico de resultados.

## Plano de acao
### 1. Modelagem e persistencia do StudyContext
- Refatorar entidades, migrations e schemas para trocar `StudyContext` por `StudyContext`, mantendo historico.
- Adicionar campos `start_date` e `end_date`, alem de um identificador de "plano" derivado para suportar multiplos planos por usuario.
- Definir politica de versionamento: novo plano replica blocos gerais (ambiente, objetivos de longo prazo) e exige apenas inputs especificos (por ex. materia, foco semanal).
- Atualizar repositorios/queries para carregar sempre o StudyContext ativo e garantir criacao imediata do plano base apos salvar o contexto.

### 2. Formulario e UX
- Reestruturar o formulario em duas etapas: (a) Contexto global reutilizavel e (b) Parametros especificos do plano atual.
- Incluir campos de datas e deixar claro para o usuario que novos planos podem herdar configuracoes existentes.
- Garantir que a submissao dispare a criacao do StudyContext e a geracao do esqueleto semanal (objetivos amplos, criterios de progresso e slots de dias vazios).

### 3. API e fluxo de dias dinamicos
- Criar/ajustar endpoints:
  - `POST /study-contexts` para criar o contexto + plano semanal de alto nivel.
  - `GET /plans/{planId}/week` retorna resumo semanal e status de cada dia.
  - `POST /plans/{planId}/days` gera um novo dia detalhado on-demand (recebe data alvo e resultados anteriores).
  - `POST /plans/{planId}/days/{dayId}/results` persiste resultados para alimentar contexto futuro.
- Implementar caching leve ou pre-validacao para evitar geracao duplicada do mesmo dia.
- Garantir que o carregamento dinamico apareca no schema (OpenAPI/GraphQL) consumido por clientes.

### 4. Ajustes de prompt e motor de IA
- Revisar prompt base para instruir a IA a:
  - Criar apenas o plano semanal de alto nivel (temas, metas, criterios) na primeira chamada.
  - Gerar dias detalhados somente quando solicitado, considerando historico de resultados e contexto futuro.
  - Valorizar adaptacoes conforme desempenho (por exemplo, repetir topicos nao dominados ou acelerar quando o aluno supera metas).
- Documentar exemplos de interacoes (primeiro plano, geracao do Dia N, ajustes apos feedback) para garantir consistencia.

### 5. Observabilidade, QA e rollout
- Adicionar eventos/telemetria para criacao de StudyContext, geracao de dias, e conclusao de atividades.
- Cobrir migrations e novas rotas com testes (unitarios + integracao) que validem a logica de geracao incremental.
- Criar checklist de rollout: executar migrations, atualizar prompts, sincronizar clientes, validar schema em staging.

## Sequenciamento proposto
1. **Semana 1** - Refatoracao de dominio: renomear entidades, migrations e atualizar formularios para coletar datas.
2. **Semana 2** - Implementar criacao imediata do plano semanal, endpoints de leitura (`/week`) e telemetria basica.
3. **Semana 3** - Liberar geracao on-demand de dias, persistencia de resultados e ajuste de prompts.
4. **Semana 4** - QA completo, testes de regressao e melhoria da documentacao + exemplos de API.

## Metricas de sucesso
- 100% dos novos planos gerados tem start/end date e StudyContext armazenado ao final do formulario.
- O endpoint `/plans/{planId}/week` responde em < 300 ms e retorna status atualizado de cada dia.
- Pelo menos 80% dos dias sao gerados sob demanda em vez de previamente, indicando uso do fluxo incremental.
- Queda nas solicitacoes de suporte relacionadas a planos desatualizados (baseline atual vs. pos-rollout).

## Riscos e mitigacao
- **Dados legados**: Precisamos migrar StudyContext existentes para StudyContext. Mitigar com script idempotente e backup.
- **Complexidade de prompt**: Ajustes podem alterar comportamento da IA. Mitigar com testes em um ambiente controlado e exemplos fixos.
- **Experiencia fragmentada**: Usuarios podem nao entender geracao sob demanda. Mitigar com onboarding explicativo e feedback visssual na UI.

## Dependencias
- Aprovacao de alteracoes no schema de API e prompts de IA.
- Disponibilidade de engenheiros para revisao de PRs e suporte durante rollout.
## Proximos passos imediatos
1. Mapear todas as ocorrencias de `StudyContext` no codigo e preparar PR de renomeacao + migrations.
2. Desenhar contrato final dos novos endpoints e atualizar schema (OpenAPI/GraphQL) antes da implementacao.
3. Escrever esqueleto dos novos prompts (primeiro plano e geracao de dia) para validacao com a equipe de produto/IA.
