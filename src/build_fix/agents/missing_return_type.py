"""
MissingReturnTypeAgent -- fixes TS7010/TS2355 missing return type errors
by reading the build log for function names and adding `: void` or `: any`
return type annotations.

Common in strict TS configs with noImplicitReturns or declaration files.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

from .base import AgentEdit, AgentResult, BaseAgent
from .utils import source_files


class MissingReturnTypeAgent(BaseAgent):
    name = "missing_return_type"
    description = "Add return type annotations to functions missing them"

    def run(self, project_root: Path, context: Optional[Dict] = None) -> AgentResult:
        build_log = ((context or {}).get("build_log") or "").strip()
        edits: List[AgentEdit] = []

        # TS7010: 'funcName', which lacks return-type annotation, implicitly has an 'any' return type.
        funcs = re.findall(
            r"['\"`](\w+)['\"`].*?lacks return-type annotation",
            build_log,
        )
        funcs += re.findall(
            r"TS7010.*?['\"`](\w+)['\"`]",
            build_log,
        )
        func_names = list(dict.fromkeys(funcs))

        if not func_names:
            return AgentResult(success=True, edits=[])

        for path in source_files(project_root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                rel = str(path.relative_to(project_root))
                new_text = text
                fixed = []

                for fname in func_names:
                    # Match function declarations without return type:
                    # function foo(args) {  -> function foo(args): void {
                    pattern = re.compile(
                        r"(function\s+" + re.escape(fname) + r"\s*\([^)]*\))\s*(\{)"
                    )
                    updated = pattern.sub(r"\1: void \2", new_text, count=1)
                    if updated != new_text:
                        new_text = updated
                        fixed.append(fname)

                if fixed and new_text != text:
                    edits.append(AgentEdit(
                        file_path=rel, old_string=text, new_string=new_text,
                        description=f"Add return type to: {', '.join(fixed)}",
                    ))
            except Exception:
                continue
        return AgentResult(success=True, edits=edits)
