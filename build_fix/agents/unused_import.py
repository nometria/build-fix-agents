"""
UnusedImportAgent — removes import lines (or individual names from destructured
imports) that are never referenced in the rest of the file.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .base import AgentEdit, AgentResult, BaseAgent
from .utils import source_files


class UnusedImportAgent(BaseAgent):
    name = "unused_import"
    description = "Remove import statements that are not used in the file"

    def run(self, project_root: Path, context: Optional[Dict] = None) -> AgentResult:
        edits: List[AgentEdit] = []
        for path in source_files(project_root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                rel = str(path.relative_to(project_root))
                edits.extend(self._remove_unused(rel, text))
            except Exception:
                continue
        return AgentResult(success=True, edits=edits)

    def _remove_unused(self, rel_path: str, text: str) -> List[AgentEdit]:
        lines = text.split("\n")
        import_idxs = [i for i, l in enumerate(lines) if re.match(r"^\s*import\s+", l)]

        for idx in import_idxs:
            line = lines[idx]
            names: Set[str] = set()
            m = re.match(r"\s*import\s+(.+?)\s+from\s+['\"].+['\"]", line)
            if m:
                part = m.group(1).strip()
                names = set(re.findall(r"\b(\w+)\b", part.strip("{}"))) if part.startswith("{") else set(re.findall(r"\b(\w+)\b", part))
            if not names:
                continue

            rest = "\n".join(lines[:idx] + lines[idx + 1:])
            used = {n for n in names if re.search(r"\b" + re.escape(n) + r"\b", rest)}
            unused = names - used

            if unused == names:
                # Whole line is dead — remove it
                new_text = "\n".join(lines[:idx] + lines[idx + 1:])
                return [AgentEdit(
                    file_path=rel_path, old_string=text, new_string=new_text,
                    description=f"Remove unused import: {line.strip()[:60]}",
                )]
            elif unused:
                # Partial — prune only unused names
                new_line = line
                for u in unused:
                    new_line = re.sub(r",\s*" + re.escape(u) + r"\b", "", new_line)
                    new_line = re.sub(r"\b" + re.escape(u) + r"\s*,", "", new_line)
                    new_line = re.sub(r"\{\s*" + re.escape(u) + r"\s*\}", "{}", new_line)
                if new_line != line:
                    new_text = "\n".join(lines[:idx] + [new_line] + lines[idx + 1:])
                    return [AgentEdit(
                        file_path=rel_path, old_string=text, new_string=new_text,
                        description=f"Remove unused import names: {unused}",
                    )]
        return []
