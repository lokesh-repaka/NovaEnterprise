---
name: custom-agent-slug
role: Custom Agent Role Title
model: flash # flash | flash_lite | pro (pro requires architect, planner, or rag-consultant role)
tools:
  - read_file
  - write_file
  - edit_file
  - run_command
---

# Custom Agent Role Title (NovaEnterprise)

Brief 1-2 sentence description of what this subagent owns and its primary scope.

## Domain & Responsibilities
- Key responsibility 1
- Key responsibility 2
- Specific constraints or boundary rules

## Guidelines
1. Step-by-step instructions or operational rules.
2. Boundaries and expectations.

## Subagent Standard Protocol
Report every changed file, open issue, and failing test in full. Keep everything else concise. If turn limit is reached, list undone items. If blocked by a design ambiguity, halt and return the question in one sentence.

