"""
ImplicitAnyAgent -- fixes TS7006 "Parameter 'x' implicitly has an 'any' type"
by adding `: any` annotation to the offending parameter.

Reads parameter names and file locations from the build log.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

from .base import AgentEdit, AgentResult, BaseAgent
from .utils import source_files


class ImplicitAnyAgent(BaseAgent):
    name = "implicit_any"
    description = "Add explicit 'any' type to parameters with implicit any"

    def run(self, project_root: Path, context: Optional[Dict] = None) -> AgentResult:
        build_log = ((context or {}).get("build_log") or "").strip()
        edits: List[AgentEdit] = []

        # Match TS7006: Parameter 'x' implicitly has an 'any' type.
        # Also match patterns like: error TS7006 ... 'paramName'
        params = re.findall(
            r"(?:TS7006|implicitly has an ['\"]any['\"] type).*?['\"`](\w+)['\"`]",
            build_log,
        )
        # Also try: Parameter 'x' implicitly has an 'any' type
        params += re.findall(
            r"Parameter\s+['\"`](\w+)['\"`]\s+implicitly\s+has\s+an\s+['\"`]any['\"`]",
            build_log,
        )
        param_names = list(dict.fromkeys(params))

        if not param_names:
            return AgentResult(success=True, edits=[])

        for path in source_files(project_root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                rel = str(path.relative_to(project_root))
                new_text = text
                fixed = []
                for param in param_names:
                    # Match param in function signatures without type annotation
                    # Handles: (param) and (param, ...) and (..., param) and (..., param, ...)
                    pattern = re.compile(
                        r"(\b" + re.escape(param) + r")(\s*[,\)=])"
                    )
                    # Only fix if param appears without a colon type annotation
                    # i.e., not already `param: something`
                    def _add_any(m: re.Match) -> str:
                        start = m.start()
                        # Check context: is this inside a function signature?
                        before = new_text[max(0, start - 200):start]
                        if "(" not in before:
                            return m.group(0)
                        # Check it doesn't already have a type
                        after_param = m.group(2)
                        if after_param.strip().startswith(":"):
                            return m.group(0)
                        return m.group(1) + ": any" + m.group(2)

                    updated = pattern.sub(_add_any, new_text)
                    if updated != new_text:
                        new_text = updated
                        fixed.append(param)

                if fixed and new_text != text:
                    edits.append(AgentEdit(
                        file_path=rel, old_string=text, new_string=new_text,
                        description=f"Add ': any' to params: {', '.join(fixed)}",
                    ))
            except Exception:
                continue
        return AgentResult(success=True, edits=edits)
