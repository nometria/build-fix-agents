"""
ExportSpellingAgent — fixes typos in export names using Levenshtein distance ≤ 2.
Reads expected symbol names from the build log.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional

from .base import AgentEdit, AgentResult, BaseAgent
from .utils import source_files


def _levenshtein(a: str, b: str) -> int:
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, m + 1):
            prev, dp[j] = dp[j], min(
                prev + (0 if a[i - 1] == b[j - 1] else 1),
                dp[j - 1] + 1,
                dp[j] + 1,
            )
    return dp[m]


class ExportSpellingAgent(BaseAgent):
    name = "export_spelling"
    description = "Fix incorrect spelling of export name using Levenshtein distance"

    def run(self, project_root: Path, context: Optional[Dict] = None) -> AgentResult:
        build_log = ((context or {}).get("build_log") or "").strip()
        edits: List[AgentEdit] = []

        expected = re.findall(
            r"exported member\s*['\"`]([A-Za-z_$][\w$]*)['\"`]", build_log
        )
        expected += re.findall(r"['\"`]([A-Za-z_$][\w$]*)['\"`].*export", build_log)

        for path in source_files(project_root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                rel = str(path.relative_to(project_root))
                for exp in expected:
                    export_match = re.search(
                        r"export\s+(?:\{\s*(\w+)\s*\}|\w+\s+(\w+)\s*[=;(])", text
                    )
                    if export_match:
                        wrong = export_match.group(1) or export_match.group(2)
                        if wrong != exp and (
                            exp in wrong or wrong in exp or _levenshtein(exp, wrong) <= 2
                        ):
                            new_text = text.replace(wrong, exp, 1)
                            if new_text != text:
                                edits.append(AgentEdit(
                                    file_path=rel, old_string=text, new_string=new_text,
                                    description=f"Fix export spelling '{wrong}' → '{exp}'",
                                ))
                                break
            except Exception:
                continue
        return AgentResult(success=True, edits=edits)
