"""
Build-fix orchestrator.

Runs all agents, deduplicates edits, applies with safety limits
(max 5 edits/file, 10 total), then optionally verifies with a build command.
Reverts on failure.
"""
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .agents import AgentEdit, get_all_agents

MAX_EDITS_PER_FILE = 5
MAX_EDITS_TOTAL = 10


def run_build(project_root: Path, build_cmd: Optional[str] = None) -> Tuple[bool, str]:
    """Run the build command. Returns (success, combined_output)."""
    cmd = build_cmd or "npm run build"
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=project_root,
            capture_output=True, text=True, timeout=300,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        return result.returncode == 0, output.strip()
    except subprocess.TimeoutExpired:
        return False, "Build timed out after 300s"
    except Exception as e:
        return False, str(e)


def apply_build_fix(
    project_root: Path,
    build_log: Optional[str] = None,
    build_cmd: Optional[str] = None,
    verify: bool = True,
) -> Dict[str, Any]:
    """
    Main entry point.

    Args:
        project_root:  Path to the project root (must contain package.json).
        build_log:     Captured build log text (improves accuracy of log-driven agents).
        build_cmd:     Shell command to verify the fix (default: `npm run build`).
        verify:        If True, run build after applying fixes and revert on failure.

    Returns:
        {
          "success": bool,
          "message": str,
          "applied_edits": [{"file_path": str, "description": str}],
          "build_verified": bool,
          "reverted": bool,
        }
    """
    root = Path(project_root).resolve()
    context: Dict[str, Any] = {}
    if build_log:
        context["build_log"] = build_log

    # Collect edits from all agents
    all_edits: List[AgentEdit] = []
    for agent in get_all_agents():
        result = agent.run(project_root=root, context=context)
        if result.edits:
            all_edits.extend(result.edits)

    # Deduplicate by (file_path, old_string)
    seen: Dict[Tuple[str, str], int] = {}
    unique: List[AgentEdit] = []
    for e in all_edits:
        key = (e.file_path, e.old_string)
        if key not in seen:
            seen[key] = len(unique)
            unique.append(e)

    # Apply per-file cap + global cap
    by_file: Dict[str, List[AgentEdit]] = {}
    for e in unique:
        by_file.setdefault(e.file_path, []).append(e)

    applied: List[AgentEdit] = []
    total = 0
    for _, edits in by_file.items():
        if total >= MAX_EDITS_TOTAL:
            break
        for e in edits[:MAX_EDITS_PER_FILE]:
            if total >= MAX_EDITS_TOTAL:
                break
            applied.append(e)
            total += 1
            if len(e.old_string) > 500:  # whole-file edit: only one per file
                break

    if total > MAX_EDITS_TOTAL:
        return _result(False, "Too many changes required. Review manually.", [], False, False)

    if not applied:
        return _result(False, "No automatic fixes found.", [], False, False)

    # Backup
    backup: Dict[str, str] = {}
    for e in applied:
        full = root / e.file_path
        if full.exists() and e.file_path not in backup:
            try:
                backup[e.file_path] = full.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # Write fixes
    try:
        for e in applied:
            full = root / e.file_path
            if not full.exists():
                continue
            current = full.read_text(encoding="utf-8", errors="replace")
            if current.strip() != e.old_string.strip():
                continue
            full.write_text(e.new_string, encoding="utf-8")
    except Exception as err:
        _revert(root, backup)
        return _result(False, f"Failed to write fixes: {err}", [], False, True)

    if not verify:
        return _result(
            True, "Fixes applied (build verification skipped).",
            [{"file_path": e.file_path, "description": e.description} for e in applied],
            False, False,
        )

    # Verify
    ok, output = run_build(root, build_cmd)
    if ok:
        return _result(
            True, "Fixes applied and build passed.",
            [{"file_path": e.file_path, "description": e.description} for e in applied],
            True, False,
        )

    _revert(root, backup)
    return _result(False, "Fixes reverted — build still failed after patching.", [], False, True,
                   build_output=output[:2000])


def _revert(root: Path, backup: Dict[str, str]) -> None:
    for rel, content in backup.items():
        try:
            (root / rel).write_text(content, encoding="utf-8")
        except Exception:
            pass


def _result(success, message, applied_edits, build_verified, reverted, build_output=""):
    return {
        "success": success,
        "message": message,
        "applied_edits": applied_edits,
        "build_verified": build_verified,
        "reverted": reverted,
        **({"build_output": build_output} if build_output else {}),
    }
