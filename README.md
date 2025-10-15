# TeacherPlus — Plataforma Educacional com IA

> Plataforma educacional interativa movida por **Inteligência Artificial Generativa**, voltada para personalizar o aprendizado e oferecer recursos integrados de **estudo, prática e avaliação** para estudantes e professores.

---

## Visão Geral

O **TeacherPlus** (ou **AI Teacher**) é uma plataforma **EdTech** desenvolvida por estudantes brasileiros de ensino médio, com o objetivo de **tornar o aprendizado mais acessível, inteligente e personalizado**.  

A aplicação utiliza **modelos de IA (Google Gemini)** para gerar planos de estudo, flashcards, quizzes e feedbacks personalizados, baseando-se no desempenho e perfil de cada aluno.
spotify
O sistema será lançado inicialmente como **MVP** até **novembro de 2025**, com foco em provas do **ENEM** e exames preparatórios.  

---

## Objetivos Principais

- **Personalização do Aprendizado**: adaptar conteúdo e ritmo ao perfil do estudante.
- **Prática Inteligente**: aplicar conceitos de _spaced repetition_ (revisão espaçada) e _active recall_ (memorização ativa).
- **Centralização de Recursos**: unir planos de estudo, flashcards e simulados em um único ambiente.
- **Automação via IA**: permitir que professores e alunos gerem conteúdos (provas, planos e resumos) automaticamente.
- **Feedback Instantâneo**: IA fornece comentários, acertos e recomendações após cada atividade.

---

## Funcionalidades Principais

### 1. Cadastro Inteligente
- Processo de **onboarding com IA**, que analisa o perfil do aluno (rotina, dificuldades e objetivos).
- Gera recomendações iniciais e planos personalizados.

### 2. Flashcards Inteligentes
- Geração automática de cartões de estudo com base nos conteúdos do ENEM.
- Sistema de **revisão espaçada (FSRS)** para memorização de longo prazo.
- Exportação em PDF via **jsPDF**.

### 3. Planos de Estudo
- Criação de planos semanais personalizados com tarefas e metas.
- IA ajusta a rotina conforme progresso e desempenho.
- Visualização em lista e calendário (futuro roadmap).

### 4. Quizzes e Simulados ENEM
- Integração com a API [enem.dev](https://enem.dev/) para gerar simulados estáticos.
- Geração de provas personalizadas com base no conteúdo estudado/desejado e contexto de usuário.
- Temporizador e feedback automatizado.
- Resultados com estatísticas de desempenho.

### 5. Painel Unificado
- Dashboard com indicadores de progresso, desempenho e revisões pendentes.
- Separação clara entre perfis de **estudante** e **professor**.

---

## Stack Tecnológica

| Camada | Tecnologias |
|--------|--------------|
| **Front-end** | Vue 3 (Composition API), TailwindCSS v4, shadcn-vue, Pinia, Axios, jsPDF, Cypress, Vitest |
| **Back-end** | Django + Django REST Framework, PostgreSQL, JWT com Cookies HttpOnly |
| **IA / Serviços** | Google Gemini SDK (Geração de conteúdo e feedback), enem.dev (Banco de questões ENEM) |
| **Infraestrutura** | Docker Compose (local), Oracle Cloud Free Tier (deploy inicial), GitHub Actions (CI/CD) |

---

## Arquitetura e Boas Práticas

- **Clean Architecture + SOLID** no backend (serviços desacoplados).
- **Feature-Sliced Design (FSD)** no front-end (organização modular por funcionalidade).
- **Design System Próprio** baseado em tokens (`NeoDash Gradient System`) e Tailwind v4.
- **Testes**:
  - **Vitest** (unitários).
  - **Cypress** (E2E).
- **Documentação** via DRF Spectacular (OpenAPI 3).

---

## Como Montar o Ambiente

### Requisitos
- Python 3.13 instalado localmente (ou Docker 26+ com Docker Compose).
- Poetry 2.1.4 (`pip install "poetry==2.1.4"`).
- Banco PostgreSQL 16+ (opcional se usar Docker Compose).

### Configuração local com Poetry
1. Duplique `.env.example` para `.env` e ajuste as variáveis (ex.: `DJANGO_SECRET_KEY`, credenciais de banco, chaves da IA).
2. Instale as dependências: `poetry install`.
3. Rode as migrações: `poetry run python manage.py migrate`.
4. Inicie o servidor de desenvolvimento: `poetry run python manage.py runserver 0.0.0.0:8000`.

### Usando Docker Compose
1. Garanta um arquivo `.env` com as credenciais necessárias. As variáveis `POSTGRES_*` já estão predefinidas para o compose.
2. Suba os contêineres: `docker compose up --build`.
3. A API ficará disponível em `http://localhost:8010` e o banco Postgres em `localhost:5433`.
4. Logs em tempo real: `docker compose logs -f web`.

> Se você estiver em Windows, prefira o Terminal WSL/WSL2 para usar o Poetry e o Docker com menos atritos de permissão.

---

## 📅 Cronograma do MVP

| Etapa | Tarefa | Período |
|-------|---------|---------|
| 1 | Finalizar cadastro inteligente (etapa 2) | Out/2025 |
| 2 | CRUD completo de Flashcards | Out/2025 |
| 3 | Planos de Estudo com IA | Out/2025 |
| 4 | Quizzes integrados ao ENEM.dev | Out/2025 |
| 5 | Testes, ajustes e documentação final | Nov/2025 |

---

## Resultados Esperados

- Melhor aproveitamento de estudo com **revisão espaçada e planos adaptativos**.
- Aprendizado mais engajador e dinâmico com **feedbacks gerados por IA**.
- Ferramenta escalável e acessível para escolas, professores e estudantes autônomos.

---

## Equipe

- **Fernando Flores** — Tech Lead, Full-Stack Developer  
- **Carlos Almada** — Back-end Developer (Python/Django)

---

## Licença

Este projeto é distribuído sob a licença **MIT**.  
Sinta-se livre para contribuir, estudar e aprimorar a plataforma.

---

## Links Importantes

- **Documentação da API ENEM**: [https://docs.enem.dev](https://docs.enem.dev)  
- **Domínio oficial**: [https://ai-teacher.plus](https://ai-teacher.plus)  
- **Design System (tokens JSON)**: `/src/shared/design-tokens/neodash.json`

---

> _“Aprender é multiplicar o poder de pensar. E o TeacherPlus nasceu para amplificar isso com inteligência.”_  
> — Projeto desenvolvido como parte do TCC técnico em Informática (2025)
