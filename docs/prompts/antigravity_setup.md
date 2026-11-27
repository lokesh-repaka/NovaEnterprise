# Antigravity (AGY) Setup: .agents/ folder structure + Context Caching & Rules for NovaEnterprise

Set up this repository's Antigravity `.agents/` folder structure, workspace rules (`GEMINI.md`), lifecycle hooks, and progressive disclosure skills tailored to the NovaEnterprise platform.

Scope: only `.agents/`, `.gitignore`, and `GEMINI.md` (or update/link from `Claude.md` if existing). Do not change application source code or mock datasets. Do not commit. Detect the OS (macOS/Linux/Windows) and use matching shell commands.

---

## Phase 0: Preconditions
1. **Antigravity CLI Check**: Run `agy --version` (or verify Antigravity IDE environment).
2. **Find Working Python**: Try `python3`, `python`, then `py -3`. Record the first valid executable as `PYTHON`.
3. **Backup**: Back up any existing `.agents/`, `.claude/`, `GEMINI.md`, and `Claude.md` to `.agents.bak-<YYYYMMDD-HHMM>/`.
4. **Inventory Existing Files**: List any files in `.agents/`. Keep pre-existing custom files untouched.

---

## Phase 1: Context Caching & Progressive Disclosure Audit
In Antigravity and Gemini 1.5/2.0/2.5+, context caching operates natively for large contexts (>32k tokens), and token efficiency is governed by **Progressive Disclosure** (skills and rules are injected on-demand or indexed; always-on rules have a 20,000-token rules budget and 24KB limit).

1. **Environment & Endpoint Check**:
   - Check process environment and shell profiles (`~/.zshrc`, `~/.bashrc`, etc.) for `GEMINI_API_KEY`, `GOOGLE_API_KEY`, or custom gateway `ANTHROPIC_BASE_URL` / `GEMINI_BASE_URL`.
   - Verify no variables are disabling caching or setting unneeded rate caps.
2. **Live Usage Check**:
   - Check the newest transcript under `<appDataDir>/brain/<conversation-id>/.system_generated/logs/transcript.jsonl` (or project logs) to verify token accounting.
3. **Verdict**: Report `ENABLED` for Native Context Caching & Progressive Disclosure.

---

## Phase 2: Model Tier Alignment
Antigravity subagents and operations use three designated model tiers:
- **`pro`** (Gemini Pro tier): High-complexity reasoning, architecture, ADRs, multi-store query routing plans.
- **`flash`** (Gemini Flash tier): Core workhorse for code generation, FastAPI/LangGraph modifications, test authoring.
- **`flash_lite`** (Gemini Flash Lite tier): High-speed, low-cost log triaging, search, and file exploration.

Ensure all subagent definitions use these standardized tiers (`pro`, `flash`, `flash_lite`, or `inherit`).

---

## Phase 3: Lifecycle Hooks (`.agents/hooks.json`)
Create or merge `.agents/hooks.json` following the Antigravity lifecycle hooks schema.

```json
{
  "pre-commit-gate": {
    "PreToolUse": [
      {
        "matcher": "run_command",
        "hooks": [
          {
            "type": "command",
            "command": "bash .agents/hooks/pre-commit.sh",
            "timeout": 30
          }
        ]
      }
    ]
  },
  "agent-guard": {
    "PreToolUse": [
      {
        "matcher": "invoke_subagent",
        "hooks": [
          {
            "type": "command",
            "command": "PYTHON .agents/hooks/agent_guard.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```
*(Replace `PYTHON` with the detected Python command from Phase 0).*

---

## Phase 4: Subagent Guard Script (`.agents/hooks/agent_guard.py`)
Create `.agents/hooks/agent_guard.py`. It inspects `invoke_subagent` calls received via standard input and enforces that the expensive `pro` tier is only invoked by allowed architectural and planning roles.

```python
"""Antigravity PreToolUse hook for invoke_subagent:
Logs subagent spawns and restricts the 'pro' model tier to authorized design roles.
Conforms to Antigravity hook stdout schema: {"decision": "allow"|"deny", "reason": "..."}
"""
import datetime
import json
import os
import sys

ALLOW_EXPENSIVE = {"architect", "planner", "rag-consultant"}
EXPENSIVE_MODELS = {"pro", "gemini-2.5-pro", "gemini-1.5-pro", "opus"}

raw = sys.stdin.read()
try:
    event = json.loads(raw)
except Exception:
    # Fail open on unparseable payload
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

tool_call = event.get("toolCall") or {}
tool_name = tool_call.get("name", "")

if tool_name != "invoke_subagent":
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

args = tool_call.get("args") or {}
agent_role = str(args.get("Role") or args.get("TypeName") or "").strip().lower()
model_choice = str(args.get("Model") or "").strip().lower()

blocked = bool(model_choice) and any(m in model_choice for m in EXPENSIVE_MODELS) and not any(a in agent_role for a in ALLOW_EXPENSIVE)

root = os.environ.get("AGY_PROJECT_DIR") or event.get("cwd") or "."
try:
    log_dir = os.path.join(root, ".agents")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "agent-calls.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "conversation_id": event.get("conversationId"),
            "role": agent_role or None,
            "model": model_choice or None,
            "blocked": blocked,
            "prompt_preview": str(args.get("Prompt", ""))[:120]
        }) + "\n")
except Exception:
    pass

if blocked:
    print(json.dumps({
        "decision": "deny",
        "reason": f"Model tier '{model_choice}' is reserved for {', '.join(sorted(ALLOW_EXPENSIVE))}. "
                  f"Run '{agent_role or 'this task'}' using 'flash' or 'flash_lite'."
    }))
else:
    print(json.dumps({"decision": "allow"}))

sys.exit(0)
```

---

## Phase 5: Folder Structure & Files
Create the following structure:
```text
GEMINI.md                          Single source of truth rules (< 24 KB / 150 lines)
.agents/
  hooks.json                       Configured in Phase 3
  hooks/
    pre-commit.sh                  Lightweight lint/test check
    agent_guard.py                 Configured in Phase 4
  agents/
    architect.md                   pro tier: Architecture & ADRs in docs/adr/
    planner.md                     pro tier: Multi-store RAG implementation plans in docs/plans/
    rag-consultant.md              pro tier: Hybrid routing & graph traversal specialist
    implementer.md                 flash tier: Code implementation in backend/, agents/, rag/
    test-engineer.md               flash tier: Targeted pytest suite in tests/
    code-reviewer.md               flash tier: Security, injection & diff review
    log-triage.md                  flash_lite tier: Pytest & CI log distillation
    explorer.md                    flash_lite tier: Read-only codebase indexing
  skills/
    plan/SKILL.md                  Workflow to generate an implementation plan
    implement/SKILL.md             Workflow to apply plan-approved changes
    test/SKILL.md                  Workflow to run targeted offline pytest suites
    review/SKILL.md                Workflow to review git diff and security boundaries
    consult-rag/SKILL.md           Workflow for specialist RAG design queries
    cost-report/SKILL.md           Audit token usage & agent-calls.jsonl
  rules/
    tests.md                       Scoped to tests/** (offline fixtures, LLM_PROVIDER=fake)
    rag-safety.md                  Scoped to rag/**, backend/** (SQL allowlist, untrusted docs)
  templates/
    agent-template.md              Template for custom subagents
```

### 5a. Subagents (`.agents/agents/`)
Tools available in Antigravity: `read_file`, `write_file`, `edit_file`, `run_command`, `manage_task`, `search_web`.

| Subagent File | Model Tier | Tools | Scope / Description |
|---|---|---|---|
| `architect.md` | `pro` | `read_file`, `write_file`, `run_command` | Architecture decisions & ADRs in `docs/adr/`. Specializes in Vector/Graph/SQL RAG separation. |
| `planner.md` | `pro` | `read_file`, `write_file`, `run_command` | Implementation plans in `docs/plans/` specifying affected files, node schemas, and test specs. |
| `rag-consultant.md` | `pro` | `read_file` | Read-only specialist for Cypher traversals, SQL allowlists, and hybrid reranking questions (< 300 words). |
| `implementer.md` | `flash` | `read_file`, `edit_file`, `write_file`, `run_command` | Implements code changes strictly adhering to approved plans in `docs/plans/`. |
| `test-engineer.md` | `flash` | `read_file`, `edit_file`, `write_file`, `run_command` | Writes & executes offline pytest tests in `tests/` (`LLM_PROVIDER=fake`). |
| `code-reviewer.md` | `flash` | `read_file`, `run_command` | Reviews `git diff` for SQL injection, untrusted document wrapping, and contract compliance. |
| `log-triage.md` | `flash_lite`| `read_file` | Extracts failing tests and tracebacks from long test logs into concise `file:line` lists. |
| `explorer.md` | `flash_lite`| `read_file` | Fast read-only mapper returning paths and line numbers without prose. |

*Standard Footer for all subagents:*
> "Report every changed file, open issue, and failing test in full. Keep everything else concise. If turn limit is reached, list undone items. If blocked by a design ambiguity, halt and return the question in one sentence."

### 5b. Skills (`.agents/skills/<name>/SKILL.md`)
All skills have frontmatter with `name` and `description` (optimized for Antigravity's progressive disclosure):
- **`plan`**: Instructions to invoke `planner` to write a step-by-step plan into `docs/plans/`.
- **`implement`**: Instructions to invoke `implementer` to execute changes from the plan.
- **`test`**: Instructions to invoke `test-engineer` with `pytest -v tests/<target>`.
- **`review`**: Instructions to invoke `code-reviewer` to run `git diff` and audit against `Claude.md` specifications.
- **`consult-rag`**: Direct inquiry to `rag-consultant` on query routing or graph schema questions.
- **`cost-report`**: Reads `.agents/agent-calls.jsonl` and summarizes subagent invocations and blocked calls.

### 5c. Scoped Rules (`.agents/rules/`)
1. **`tests.md`**:
   ```markdown
   ---
   trigger: glob
   globs: "**/tests/**, **/*_test.py, **/test_*.py"
   ---
   # Test Guidelines (NovaEnterprise)
   - All tests must run offline with no external network: LLM_PROVIDER=fake, VECTOR_STORE=memory, GRAPH_STORE=memory.
   - Use pytest fixtures for database sessions and mocked redis.
   - Assert exact citation resolving and evidence shapes on RAG endpoints.
   ```
2. **`rag-safety.md`**:
   ```markdown
   ---
   trigger: glob
   globs: "**/rag/**, **/backend/app/**, **/agents/**"
   ---
   # RAG & Security Guidelines (NovaEnterprise)
   - Never execute unvalidated SQL: all queries must pass validate_sql() against the allowlist schema.
   - Untrusted documents (e.g. vendor notes) must be wrapped and never executed as agent instructions.
   - Cypher queries must use typed graph traversals.
   ```

### 5d. GEMINI.md
Keep under 150 lines (or < 24 KB).
- Point to `Claude.md` as the authoritative domain and architecture specification for NovaEnterprise.
- Outline the core layer rules (`api → services → repositories → models`, `agents / rag / memory → app.core`).
- Quick routing table:
  - Plan complex RAG tasks → `/plan`
  - Implement approved changes → `/implement`
  - Run / write tests → `/test`
  - Inspect diff & security → `/review`
  - RAG routing ambiguity → `/consult-rag`

---

## Phase 6: `.gitignore`
Append these lines if missing:
```gitignore
# Antigravity artifacts & logs
/.agents/agent-calls.jsonl
/.agents.bak-*/
/GEMINI.local.md
/data/enterprise.db
```

---

## Phase 7: Verification
1. **JSON Validation**: Validate `.agents/hooks.json` syntax via `python -m json.tool .agents/hooks.json`.
2. **Hook Self-Test**:
   - Pipe `{"toolCall": {"name": "invoke_subagent", "args": {"Model": "pro", "Role": "general-worker"}}}` into `agent_guard.py` → Must output `{"decision": "deny", ...}`.
   - Pipe `{"toolCall": {"name": "invoke_subagent", "args": {"Model": "pro", "Role": "planner"}}}` into `agent_guard.py` → Must output `{"decision": "allow"}`.
   - Clean up `.agents/agent-calls.jsonl` test entries.
3. Check `git status --short`.

---

## Phase 8: Execution Summary
Report:
- Caching & Progressive disclosure status.
- Files created, backed up, and updated.
- Results of the `agent_guard.py` verification tests.
- Confirmation of `.agents/` layout ready for NovaEnterprise development.