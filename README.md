# build-fix

> Auto-repair TypeScript / JavaScript build errors in one command.

Parses your build log and surgically patches source files. Zero config, zero dependencies.

---

## What it fixes

| Agent | Trigger | Fix |
|-------|---------|-----|
| `unused_import` | Import name never referenced in file | Removes entire line or individual names |
| `duplicate_var` | `const X` / `function X` declared twice | Renames second occurrence to `X_2` |
| `missing_export` | Build log: `X is not exported` | Adds `export` keyword to the declaration |
| `export_spelling` | Build log: `expected X, found Y` | Fixes typo using Levenshtein distance ≤ 2 |

Safety: applies at most **5 edits per file** and **10 edits total**. Reverts everything if the build still fails after patching.

---

## Install

```bash
pip install build-fix          # PyPI (coming soon)

# or run from source:
git clone https://github.com/YOUR_ORG/build-fix
cd build-fix
pip install -e .
```

---

## Usage

```bash
# Scan current directory, apply fixes, verify with `npm run build`
build-fix .

# Provide a captured build log for more accurate fixes
npm run build 2>&1 | tee build.log
build-fix . --log build.log

# Custom build command
build-fix . --cmd "pnpm build"

# Apply without running build verification
build-fix . --no-verify

# JSON output (for CI integration)
build-fix . --json
```

---

## Extend with custom agents

```python
from build_fix.agents.base import BaseAgent, AgentEdit, AgentResult
from pathlib import Path

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Fix something custom"

    def run(self, project_root: Path, context=None) -> AgentResult:
        # Find files, propose edits
        return AgentResult(success=True, edits=[...])
```

Register in `src/agents/__init__.py → get_all_agents()`.

---

## Immediate next steps (to productionise)
1. Publish to PyPI: `pip install build-fix`
2. Publish to npm as a wrapper: `npx build-fix .`
3. Add a VS Code extension that runs on save-with-errors
4. Add GitHub Action: auto-runs on failed CI builds and opens a PR with fixes

---

## Commercial viability
- VS Code extension marketplace: $5–9/mo subscription
- GitHub App: auto-fix PR on CI failure — charge per repo/seat
- Cursor / Windsurf plugin: native AI-fix integration
