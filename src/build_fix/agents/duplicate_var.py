"""
DuplicateVarAgent - renames the second occurrence of a duplicate const/let/var/function
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

        # Compute brace-nesting depth at every offset so we can restrict
        # duplicate detection to declarations at the SAME scope. Two `const x`
        # in different functions (different scopes) are valid JavaScript and
        # must NOT be flagged.
        depth_at: List[int] = [0] * (len(text) + 1)
        depth = 0
        # Track whether we're inside a string/template/comment to skip braces there
        i = 0
        in_block_comment = False
        in_line_comment = False
        in_string = None  # None or quote char
        in_template = 0   # template-literal nesting (with ${} expressions)
        while i < len(text):
            c = text[i]
            depth_at[i] = depth
            if in_block_comment:
                if c == "*" and i + 1 < len(text) and text[i+1] == "/":
                    in_block_comment = False
                    i += 2
                    continue
            elif in_line_comment:
                if c == "\n":
                    in_line_comment = False
            elif in_string:
                if c == "\\" and i + 1 < len(text):
                    i += 2
                    continue
                if c == in_string:
                    in_string = None
            elif in_template:
                # In template literal - `}` closes ${} expression; ` closes literal
                if c == "`":
                    in_template -= 1
                elif c == "$" and i + 1 < len(text) and text[i+1] == "{":
                    # entering ${} - treat as code (depth tracked)
                    depth += 1
                    i += 2
                    continue
            else:
                if c == "/" and i + 1 < len(text):
                    nxt = text[i+1]
                    if nxt == "/":
                        in_line_comment = True
                        i += 2
                        continue
                    if nxt == "*":
                        in_block_comment = True
                        i += 2
                        continue
                if c == '"' or c == "'":
                    in_string = c
                elif c == "`":
                    in_template += 1
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth = max(0, depth - 1)
            i += 1
        depth_at[len(text)] = depth

        # Only flag TOP-LEVEL duplicates (depth=0). Two `const foo` declarations
        # in different functions or different `if` blocks are valid JavaScript
        # (block-scoped) and must NOT be flagged as duplicates.
        declarations: List[Tuple[int, str]] = []
        for m in decl_pattern.finditer(text):
            name = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            if name and not name.startswith("_") and depth_at[m.start()] == 0:
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
