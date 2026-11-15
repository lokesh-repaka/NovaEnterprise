#!/usr/bin/env bash
set -eo pipefail

# Lightweight pre-commit gate for NovaEnterprise
# Fast syntax check on Python files

if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
else
    echo "[pre-commit] Python interpreter not found, skipping py_compile check."
    exit 0
fi

# Check modified / untracked Python files if git is available
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    CHANGED_FILES=$(git diff --name-only --diff-filter=d HEAD 2>/dev/null | grep -E '\.py$' || true)
    UNTRACKED_FILES=$(git ls-files --others --exclude-standard 2>/dev/null | grep -E '\.py$' || true)
    FILES_TO_CHECK=$(echo -e "${CHANGED_FILES}\n${UNTRACKED_FILES}" | sed '/^$/d' | sort -u)
else
    # Fallback: check all python files up to 3 levels deep excluding hidden dirs / venv
    FILES_TO_CHECK=$(find . -maxdepth 3 -name "*.py" -not -path "*/.*" -not -path "*/venv/*" 2>/dev/null || true)
fi

if [ -n "$FILES_TO_CHECK" ]; then
    for f in $FILES_TO_CHECK; do
        if [ -f "$f" ]; then
            $PY_BIN -m py_compile "$f" 2>&1 || {
                echo "[pre-commit] Syntax error in $f"
                exit 1
            }
        fi
    done
fi

exit 0

