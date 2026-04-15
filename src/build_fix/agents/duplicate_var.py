"""
DuplicateVarAgent — renames the second occurrence of a duplicate const/let/var/function
declaration in the same file to `<name>_2`.
"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .base import AgentEdit, AgentResult, BaseAgent
from .utils import source_files


class DuplicateVarAgent(BaseAgent):
    name = "duplicate_var"
    description = "Rename duplicate variable declarations in a file"

    def run(self, project_root: Path, context: Optional[Dict] = None) -> AgentResult:
        edits: List[AgentEdit] = []
        for path in source_files(project_root):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                rel = path.relative_to(project_root)
                edits.extend(self._find_duplicates(str(rel), text))
            except Exception:
                continue
        return AgentResult(success=True, edits=edits)

    def _find_duplicates(self, rel_path: str, text: str) -> List[AgentEdit]:
        decl_pattern = re.compile(
            r"(?:(?:export)\s+)?(?:const|let|var)\s+(\w+)\s*[=;]|"
            r"function\s+(\w+)\s*\(|"
            r"(?:export\s+)?function\s+(\w+)\s*\("
        )
        declarations: List[Tuple[int, str]] = []
        for m in decl_pattern.finditer(text):
            name = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            if name and not name.startswith("_"):
                declarations.append((m.start(), name))

        seen: Dict[str, List[int]] = {}
        for pos, name in declarations:
            seen.setdefault(name, []).append(pos)

        for name, positions in seen.items():
            if len(positions) <= 1:
                continue
            pos = positions[1]
            new_name = f"{name}_2"
            line_end = text.find("\n", pos)
            if line_end == -1:
                line_end = len(text)
            decl_line = text[pos:line_end]
            # Try const/let/var pattern first
            old_decl = re.compile(
                r"((?:export\s+)?(?:const|let|var)\s+)" + re.escape(name) + r"(\s*[=;])"
            )
            decl_new, n = old_decl.subn(r"\g<1>" + new_name + r"\g<2>", decl_line, count=1)
            if not n:
                # Try function declaration pattern
                func_decl = re.compile(
                    r"((?:export\s+)?function\s+)" + re.escape(name) + r"(\s*\()"
                )
                decl_new, n = func_decl.subn(r"\g<1>" + new_name + r"\g<2>", decl_line, count=1)
            if not n:
                continue
            before = text[:pos]
            after = text[line_end:]
            after_replaced = re.sub(r"\b" + re.escape(name) + r"\b", new_name, after)
            new_string = before + decl_new + after_replaced
            if new_string != text:
                return [AgentEdit(
                    file_path=rel_path,
                    old_string=text,
                    new_string=new_string,
                    description=f"Rename duplicate '{name}' → '{new_name}'",
                )]
        return []
