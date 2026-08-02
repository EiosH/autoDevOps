# AutoDevOps

A multi-agent orchestration platform for local-model-driven code generation and DevOps automation.

AutoDevOps is designed for private / on-prem environments. Agents plan work as a DAG, collaborate by role (dev / test / review), call tools through a skill layer, and persist short-term, episodic, and long-term memory. Inference goes through a pluggable LLM gateway so business logic never depends on a specific backend (Ollama, vLLM, etc.).

## Highlights

- **Task planner** — turns a user goal into a DAG of subtasks
- **Multi-agent scheduler** — routes work by `AgentCard` role; retries and review–fix loops included
- **Step snapshots** — every step records input, output, and status for retry / rollback
- **Code generation loop** — generate → review → fix until acceptance criteria are met
- **Local LLM gateway** — swap providers without changing agents
- **Memory system** — short-term tool traces, episodic step summaries, long-term distilled lessons
- **Skills over raw tools** — agents choose skills; skills compose low-level tools

## Architecture

```text
API layer            FastAPI / WebSocket / SSE          (planned)
Orchestration        Planner / Scheduler / AgentRunner
Agents               DevAgent / TestAgent / ReviewAgent (+ more planned)
Skills               code_write / code_refactor / code_review / run_test
Tools                read_file / write_patch / delete_file / git_diff / run_tests / …
LLM gateway          LLMProvider → Ollama / vLLM / Mock
Memory               short-term / episodic / long-term (file or PostgreSQL)
Data                 PostgreSQL (+ pgvector planned) / Redis (planned)
Governance           traces / metrics / eval suite / audit / sandbox (planned)
```

### Current project layout

```text
src/
  agents/       Role agents (dev, test, review) + AgentCard
  core/         Planner, scheduler, models, agent runner
  engine/       LLMProvider implementations (Ollama, vLLM)
  memory/       Memory store, backends, long-term distillation
  skills/       High-level workflows agents can invoke
  tools/        Low-level tools (files, git, tests, shell)
  utils/        Path helpers
  main.py       Entry point wiring registry + scheduler
workspace/      Working tree agents edit for demo tasks
```

## Core loop

```text
User goal
  → Planner builds a task DAG
  → Scheduler recalls long-term memory
  → DevAgent edits code via skills
  → ReviewAgent / TestAgent verify
  → On failure: record feedback, re-run dev → review (fix cycle)
  → Promote durable lessons into long-term memory
  → Emit execution report
```

## Tech choices

| Area | Choice | Notes |
|------|--------|--------|
| Local inference | Ollama (dev) / vLLM (prod target) | Unified `LLMProvider` interface |
| Agent framework | Custom scheduler | LangChain pieces optional; core orchestration is first-party |
| Short-term memory | In-run context | Recent tool calls and step state |
| Long-term memory | PostgreSQL or file backend | Preferences, fix lessons, conventions |
| Semantic memory | pgvector / similar (planned) | Code chunks + embeddings for repo understanding |
| Tools | Local registry today → MCP later | Avoid hardcoding tools into agents |

## Getting started

### Requirements

- Python 3.11+
- A local LLM endpoint (Ollama by default)
- Optional: PostgreSQL for durable long-term memory

### Install

```bash
pip install -r requirements.txt
```

### Configure LLM

Default entry point uses `OllamaProvider` (`http://127.0.0.1:11434`). Switch to vLLM by changing the provider in `src/main.py`:

```python
llm = OllamaProvider()
# llm = vLLMProvider()
```

### Run

```bash
cd src
python main.py
```

Edit `user_goal` in `main.py` to try different tasks against `workspace/`.

## Memory model

| Type | Scope | Purpose |
|------|--------|---------|
| Short-term | Current run | Recent tool calls; avoid repeating failures |
| Episodic | Current run | Step summaries and review feedback |
| Long-term | Cross-run | Distilled preferences, fix lessons, conventions |
| Semantic | Repo-level (planned) | Retrieved code context via embeddings |

Long-term memory is recalled at run start and promoted after a successful run when durable lessons exist.

## Roadmap

### Phase 1 — Orchestration MVP ✅

Task / AgentResult / StepSnapshot / AgentCard / BaseAgent / Scheduler / MemoryStore.

### Phase 2 — Local LLM gateway ✅

`LLMProvider` with `generate` / `chat` / `stream` / `structured_output`, plus Ollama and vLLM providers.

### Phase 3 — Repository understanding

Scan → chunk → embed → vector search → (optional) rerank → context packer. Index is a **locator**, not a source of truth; agents still `read_file` before editing.

### Phase 4 — MCP tool layer

Expose tools via MCP (`read_file`, `write_file`, `search_code`, `run_tests`, `git_diff`, `shell_exec_safe`) instead of direct function calls.

### Phase 5 — Full code-generation loop

```text
Planner → CodeContextRetriever → DevAgent → TestAgent → Eval / Debug → diff + report
```

### Phase 6 — Enterprise hardening

- Audit log of tasks and file changes
- Approval gates for high-risk tools
- Sandboxed test / shell execution
- Observability: trace id, latency, token usage, tool logs
- Eval suite: fixed ~10 coding tasks with objective graders (pytest / file / content assertions)
- Config center for models, tools, and agent policies

## Evaluation (planned)

Benchmark cases live under an `evaluation/` package:

1. Isolated fixture workspace per case
2. Run the full agent pipeline
3. Grade with **objective** checks (pytest, file existence, content constraints)
4. Report suite success rate (`pass@1` / `pass@k`)

LLM review can remain part of the runtime loop but should not be the sole pass/fail signal for the benchmark.

## Status

Working today: planner, multi-agent scheduler with review–fix cycles, Ollama/vLLM providers, skill/tool layers, and long-term memory (file or PostgreSQL).

Next focus: repository indexing / retrieval, MCP tooling, and an automated eval suite.
