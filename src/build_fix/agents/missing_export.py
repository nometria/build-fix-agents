"""
MissingExportAgent -- reads build log for "X is not exported" patterns
and adds `export` to matching declarations.

Improved: also handles class, interface, type, and enum declarations.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

from .base import AgentEdit, AgentResult, BaseAgent
from .utils import source_files


class MissingExportAgent(BaseAgent):
    name = "missing_export"
    description = "Add export to symbol that is imported elsewhere"

    def run(self, project_root: Path, context: Optional[Dict] = None) -> AgentResult:
        build_log = ((context or {}).get("build_log") or "").strip()
        edits: List[AgentEdit] = []

        not_exported = re.findall(
            r"(?:exported member|is not exported|is not a function)[\s'\"`]*([A-Za-z_$][\w$]*)",
            build_log,
        )
        not_exported += re.findall(
            r"['\"`]([A-Za-z_$][\w$]*)['\"`]\s*is not exported", build_log
        )
        # Also match TS2305: Module '"./foo"' has no exported member 'Bar'.
        not_exported += re.findall(
            r"has no exported member\s*['\"`]([A-Za-z_$][\w$]*)['\"`]", build_log
        )
        symbols = list(dict.fromkeys(not_exported))

        for path in source_files(project_root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                rel = str(path.relative_to(project_root))
                for symbol in symbols:
                    if re.search(r"^\s*export\s+.*\b" + re.escape(symbol) + r"\b", text, re.M):
                        continue
                    for pattern, replacement in [
                        (r"^(\s*)(const\s+" + re.escape(symbol) + r"\s*[=;:])", r"\1export \2"),
                        (r"^(\s*)(let\s+" + re.escape(symbol) + r"\s*[=;:])", r"\1export \2"),
                        (r"^(\s*)(var\s+" + re.escape(symbol) + r"\s*[=;:])", r"\1export \2"),
                        (r"^(\s*)(function\s+" + re.escape(symbol) + r"\s*[\(<])", r"\1export \2"),
                        (r"^(\s*)(class\s+" + re.escape(symbol) + r"[\s{<])", r"\1export \2"),
                        (r"^(\s*)(interface\s+" + re.escape(symbol) + r"[\s{<])", r"\1export \2"),
                        (r"^(\s*)(type\s+" + re.escape(symbol) + r"\s*[=<])", r"\1export \2"),
                        (r"^(\s*)(enum\s+" + re.escape(symbol) + r"[\s{])", r"\1export \2"),
                    ]:
                        new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
                        if n:
                            edits.append(AgentEdit(
                                file_path=rel, old_string=text, new_string=new_text,
                                description=f"Export '{symbol}'",
                            ))
                            break
            except Exception:
                continue
        return AgentResult(success=True, edits=edits)
