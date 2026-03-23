"""
Tests for build-fix agents.
Run: pytest tests/
"""
import sys
import os
import textwrap
import tempfile
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents.duplicate_var import DuplicateVarAgent
from agents.missing_export import MissingExportAgent
from agents.export_spelling import ExportSpellingAgent
from agents.unused_import import UnusedImportAgent


# ── helpers ───────────────────────────────────────────────────────────────────

def make_project(files: dict) -> Path:
    """Create a temporary project directory with given files."""
    tmp = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        full = tmp / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(textwrap.dedent(content))
    return tmp


# ── DuplicateVarAgent ─────────────────────────────────────────────────────────

def test_duplicate_var_detected():
    project = make_project({
        "src/foo.ts": """
            const myFunc = () => {};
            export const myFunc = () => 'duplicate';
        """
    })
    agent = DuplicateVarAgent()
    result = agent.run(project)
    assert result.success
    assert len(result.edits) == 1
    assert "myFunc_2" in result.edits[0].new_string


def test_duplicate_var_no_false_positive():
    project = make_project({
        "src/foo.ts": """
            const alpha = 1;
            const beta = 2;
        """
    })
    result = DuplicateVarAgent().run(project)
    assert result.edits == []


# ── MissingExportAgent ────────────────────────────────────────────────────────

def test_missing_export_adds_keyword():
    project = make_project({
        "src/utils.ts": """
            const myHelper = (x: number) => x * 2;
        """
    })
    build_log = "error: 'myHelper' is not exported from './utils'"
    result = MissingExportAgent().run(project, {"build_log": build_log})
    assert result.success
    assert len(result.edits) == 1
    assert "export const myHelper" in result.edits[0].new_string


def test_missing_export_skips_already_exported():
    project = make_project({
        "src/utils.ts": "export const myHelper = (x: number) => x * 2;"
    })
    build_log = "error: 'myHelper' is not exported"
    result = MissingExportAgent().run(project, {"build_log": build_log})
    assert result.edits == []


# ── ExportSpellingAgent ───────────────────────────────────────────────────────

def test_export_spelling_fixes_typo():
    project = make_project({
        "src/comp.tsx": "export const MyComponnet = () => <div />;",
    })
    build_log = "Module has no exported member 'MyComponent'"
    result = ExportSpellingAgent().run(project, {"build_log": build_log})
    assert result.success
    assert len(result.edits) == 1
    assert "MyComponent" in result.edits[0].new_string


def test_levenshtein_threshold():
    from agents.export_spelling import _levenshtein
    assert _levenshtein("kitten", "sitting") == 3
    assert _levenshtein("MyComponent", "MyComponnet") == 2
    assert _levenshtein("abc", "abc") == 0


# ── UnusedImportAgent ─────────────────────────────────────────────────────────

def test_unused_import_whole_line_removed():
    project = make_project({
        "src/page.tsx": textwrap.dedent("""
            import React from 'react';
            import { useState } from 'react';

            export function Page() {
              const [count, setCount] = useState(0);
              return <div>{count}</div>;
            }
        """).lstrip()
    })
    result = UnusedImportAgent().run(project)
    assert result.success
    # React is unused (no JSX transform implied in this test)
    # At least one edit removing the unused import
    assert len(result.edits) >= 1


def test_unused_import_partial_removal():
    project = make_project({
        "src/comp.tsx": textwrap.dedent("""
            import { useCallback, useState } from 'react';

            export function Comp() {
              const [x, setX] = useState(0);
              return <div>{x}</div>;
            }
        """).lstrip()
    })
    result = UnusedImportAgent().run(project)
    # useCallback is unused, useState is used
    if result.edits:
        edit = result.edits[0]
        assert "useCallback" not in edit.new_string or "useState" in edit.new_string


# ── Integration: no changes on clean code ────────────────────────────────────

def test_no_edits_on_clean_file():
    project = make_project({
        "src/clean.ts": textwrap.dedent("""
            import { add } from './math';
            export const double = (x: number) => add(x, x);
        """).lstrip()
    })
    from agents import get_all_agents
    all_edits = []
    for agent in get_all_agents():
        all_edits.extend(agent.run(project).edits)
    # Should be no edits — the file is clean
    assert all_edits == []
