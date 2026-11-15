---
name: cost-report
description: Audit subagent invocations, model tier allocations, and blocked calls logged in .agents/agent-calls.jsonl.
---

# Cost & Model Tier Audit Workflow (NovaEnterprise)

Use this skill to inspect model tier usage, ensure expensive `pro` models are reserved for authorized design roles, and review subagent invocation logs.

## Workflow Steps

1. **Verify Log Existence**:
   - Check if `.agents/agent-calls.jsonl` exists in the repository root.
   - If missing, report that no subagents have been invoked yet during this session.

2. **Analyze Invocation Metrics**:
   - Run a summary script on `.agents/agent-calls.jsonl` to aggregate:
     - Total subagent calls by model tier (`pro`, `flash`, `flash_lite`).
     - Breakdown by role (`architect`, `planner`, `implementer`, etc.).
     - Count of blocked invocations (attempts to use `pro` tier by unauthorized roles).
     - Recent call timestamps and prompt previews.

3. **Sample Triage Command**:
   ```bash
   python3 -c "
   import json, os
   log_path = '.agents/agent-calls.jsonl'
   if not os.path.exists(log_path):
       print('No agent calls logged yet.')
   else:
       with open(log_path, 'r', encoding='utf-8') as f:
           records = [json.loads(line) for line in f if line.strip()]
       print(f'Total invocations logged: {len(records)}')
       models = {}
       roles = {}
       blocked = 0
       for r in records:
           m = r.get('model', 'unspecified')
           models[m] = models.get(m, 0) + 1
           role = r.get('role', 'unspecified')
           roles[role] = roles.get(role, 0) + 1
           if r.get('blocked'):
               blocked += 1
       print(f'Model distribution: {models}')
       print(f'Role distribution: {roles}')
       print(f'Blocked calls: {blocked}')
   "
   ```

4. **Remediate Tier Misalignments**:
   - If non-design tasks attempted to use `pro`, redirect them to `flash` or `flash_lite`.

