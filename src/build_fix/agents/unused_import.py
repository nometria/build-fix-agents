"""
UnusedImportAgent - removes import lines (or individual names from destructured
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
        import_idxs = [i for i, ln in enumerate(lines) if re.match(r"^\s*import\s+", ln)]

        # Detect JSX usage: opening tags like <Foo>, <foo>, <Foo />, <>, fragments
        # Files using JSX with the classic transform need React in scope; we must
        # never strip the default `React` import from such files.
        non_import_text = "\n".join(ln for i, ln in enumerate(lines) if i not in import_idxs)
        has_jsx = bool(re.search(r"<[A-Za-z][\w.]*[\s/>]|<>|</", non_import_text))

        # Names whose import we never strip (implicit usage, side-effect, JSX)
        ALWAYS_USED = {"React"} if has_jsx else set()

        # Collect ALL dead import lines, then remove them in one edit
        dead_lines: List[int] = []
        partial_edits: List[tuple] = []  # (line_idx, new_line)

        for idx in import_idxs:
            line = lines[idx]
            # Skip side-effect imports: `import 'foo'` / `import "foo"`
            if re.match(r"^\s*import\s+['\"]", line):
                continue
            # Skip type-only imports - TS may keep them for declaration files
            if re.match(r"^\s*import\s+type\b", line):
                continue
            names: Set[str] = set()
            m = re.match(r"\s*import\s+(.+?)\s+from\s+['\"].+['\"]", line)
            if m:
                part = m.group(1).strip()
                names = set(re.findall(r"\b(\w+)\b", part.strip("{}"))) if part.startswith("{") else set(re.findall(r"\b(\w+)\b", part))
            if not names:
                continue
            # Drop implicit-use names from "unused" consideration
            considered = names - ALWAYS_USED
            if not considered:
                continue

            used = {n for n in considered if re.search(r"\b" + re.escape(n) + r"\b", non_import_text)}
            unused = considered - used

            if unused == considered and not (names & ALWAYS_USED):
                # All considered names unused AND no implicit-use names - remove line
                dead_lines.append(idx)
            elif unused:
                new_line = line
                for u in unused:
                    new_line = re.sub(r",\s*" + re.escape(u) + r"\b", "", new_line)
                    new_line = re.sub(r"\b" + re.escape(u) + r"\s*,", "", new_line)
                    new_line = re.sub(r"\{\s*" + re.escape(u) + r"\s*\}", "{}", new_line)
                if new_line != line:
                    partial_edits.append((idx, new_line))

        if not dead_lines and not partial_edits:
            return []

        # Apply all changes in one pass
        new_lines = list(lines)
        for idx, new_line in partial_edits:
            new_lines[idx] = new_line

        # Remove dead lines in reverse so indices stay valid
        for idx in sorted(dead_lines, reverse=True):
            del new_lines[idx]

        new_text = "\n".join(new_lines)
        if new_text == text:
            return []

        removed = [lines[i].strip()[:50] for i in dead_lines]
        pruned = [f"pruned names in line {i}" for i, _ in partial_edits]
        desc_parts = removed + pruned
        return [AgentEdit(
            file_path=rel_path, old_string=text, new_string=new_text,
            description=f"Remove unused imports: {', '.join(desc_parts[:3])}",
        )]
