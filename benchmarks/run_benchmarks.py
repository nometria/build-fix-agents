#!/usr/bin/env python3
"""
build-fix benchmark suite.

Creates synthetic TypeScript/JS projects with known build errors,
runs each agent, and measures:
  - Fix success rate per error type
  - Fix accuracy (does the fix resolve the error?)
  - Processing speed
"""
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

# Add src to path so we can import build_fix
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from build_fix.agents.unused_import import UnusedImportAgent
from build_fix.agents.duplicate_var import DuplicateVarAgent
from build_fix.agents.missing_export import MissingExportAgent
from build_fix.agents.export_spelling import ExportSpellingAgent


# ── Test fixtures ────────────────────────────────────────────────────────

UNUSED_IMPORT_CASES = [
    {
        "name": "single_unused_default",
        "file": "app.tsx",
        "content": 'import React from "react";\nimport axios from "axios";\n\nconst App = () => <div>Hello</div>;\nexport default App;\n',
        "expected_removed": "axios",
    },
    {
        "name": "multiple_unused_named",
        "file": "utils.ts",
        "content": 'import { useState, useEffect, useCallback } from "react";\n\nfunction Component() {\n  const [x, setX] = useState(0);\n  return x;\n}\n',
        "expected_removed": "useCallback",
    },
    {
        "name": "all_unused",
        "file": "dead.ts",
        "content": 'import { format } from "date-fns";\nimport lodash from "lodash";\n\nconst x = 42;\nexport default x;\n',
        "expected_removed": "format",
    },
    {
        "name": "type_import_unused",
        "file": "types.ts",
        "content": 'import { User, Post, Comment } from "./models";\n\nfunction getUser(): User {\n  return { id: 1, name: "test" };\n}\nexport { getUser };\n',
        "expected_removed": "Comment",
    },
    {
        "name": "no_unused",
        "file": "clean.ts",
        "content": 'import { useState } from "react";\n\nfunction Component() {\n  const [v] = useState(0);\n  return v;\n}\nexport { Component };\n',
        "expected_removed": None,  # Nothing should be removed
    },
]

DUPLICATE_VAR_CASES = [
    {
        "name": "duplicate_const",
        "file": "config.ts",
        "content": 'const API_URL = "http://localhost:3000";\nconst DEBUG = true;\nconst API_URL = "http://prod.example.com";\n\nexport { API_URL, DEBUG };\n',
        "expected_rename": "API_URL",
    },
    {
        "name": "duplicate_function",
        "file": "helpers.ts",
        "content": 'function formatDate(d: Date) {\n  return d.toISOString();\n}\nfunction formatDate(d: Date) {\n  return d.toLocaleDateString();\n}\nexport { formatDate };\n',
        "expected_rename": "formatDate",
    },
    {
        "name": "duplicate_let",
        "file": "state.ts",
        "content": 'let counter = 0;\nlet name = "test";\nlet counter = 10;\n\nexport { counter, name };\n',
        "expected_rename": "counter",
    },
    {
        "name": "no_duplicates",
        "file": "clean.ts",
        "content": 'const a = 1;\nconst b = 2;\nconst c = 3;\nexport { a, b, c };\n',
        "expected_rename": None,
    },
]

MISSING_EXPORT_CASES = [
    {
        "name": "missing_const_export",
        "file": "api.ts",
        "content": 'const fetchUser = async (id: number) => {\n  return fetch(`/api/user/${id}`);\n};\n\nexport const API_BASE = "/api";\n',
        "build_log": "Module './api' has no exported member 'fetchUser'",
        "expected_export": "fetchUser",
    },
    {
        "name": "missing_function_export",
        "file": "utils.ts",
        "content": 'function calculateTotal(items: number[]) {\n  return items.reduce((a, b) => a + b, 0);\n}\n\nexport const VERSION = "1.0";\n',
        "build_log": "'calculateTotal' is not exported from './utils'",
        "expected_export": "calculateTotal",
    },
    {
        "name": "already_exported",
        "file": "lib.ts",
        "content": 'export const helper = () => {};\n',
        "build_log": "'helper' is not exported from './lib'",
        "expected_export": None,  # Already exported, nothing to do
    },
]

EXPORT_SPELLING_CASES = [
    {
        "name": "typo_one_char",
        "file": "components.ts",
        "content": 'export const Buttn = () => {};\n',
        "build_log": "exported member 'Button' not found",
        "expected_fix": ("Buttn", "Button"),
    },
    {
        "name": "typo_two_chars",
        "file": "hooks.ts",
        "content": 'export function useAuhentication() {}\n',
        "build_log": "exported member 'useAuthentication' not found",
        "expected_fix": ("useAuhentication", "useAuthentication"),
    },
    {
        "name": "no_typo",
        "file": "clean.ts",
        "content": 'export const Button = () => {};\n',
        "build_log": "exported member 'Button' not found",
        "expected_fix": None,  # Name matches, no fix
    },
]


def run_agent_test(agent, cases, uses_build_log=False):
    """Run an agent against test cases and measure results."""
    results = []

    for case in cases:
        tmpdir = tempfile.mkdtemp(prefix="buildfix_bench_")
        try:
            # Create package.json (required for source_files detection)
            (Path(tmpdir) / "package.json").write_text('{"name": "test"}')

            # Write test file
            filepath = Path(tmpdir) / case["file"]
            filepath.write_text(case["content"])

            context = {}
            if uses_build_log and "build_log" in case:
                context["build_log"] = case["build_log"]

            start = time.perf_counter()
            result = agent.run(project_root=Path(tmpdir), context=context)
            elapsed = time.perf_counter() - start

            has_edits = bool(result.edits)
            expects_change = case.get("expected_removed") is not None or \
                             case.get("expected_rename") is not None or \
                             case.get("expected_export") is not None or \
                             case.get("expected_fix") is not None

            # Check if the fix is correct
            correct = False
            if not expects_change and not has_edits:
                correct = True  # Correctly did nothing
            elif expects_change and has_edits:
                edit = result.edits[0]
                if "expected_removed" in case and case["expected_removed"]:
                    correct = case["expected_removed"] not in edit.new_string or \
                              f"import {case['expected_removed']}" not in edit.new_string
                elif "expected_rename" in case and case["expected_rename"]:
                    correct = f"{case['expected_rename']}_2" in edit.new_string
                elif "expected_export" in case and case["expected_export"]:
                    correct = f"export" in edit.new_string and case["expected_export"] in edit.new_string
                elif "expected_fix" in case and case["expected_fix"]:
                    old_name, new_name = case["expected_fix"]
                    correct = new_name in edit.new_string and old_name not in edit.new_string

            results.append({
                "name": case["name"],
                "expected_change": expects_change,
                "produced_edit": has_edits,
                "correct": correct,
                "time_ms": round(elapsed * 1000, 2),
            })
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return results


def main():
    print("=" * 60)
    print("build-fix Benchmark Suite")
    print("=" * 60)

    all_results = {}

    # ── Unused Import Agent ──
    print("\n📋 Unused Import Agent")
    print("-" * 40)
    agent = UnusedImportAgent()
    results = run_agent_test(agent, UNUSED_IMPORT_CASES)
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    detected = sum(1 for r in results if r["produced_edit"] == r["expected_change"])
    avg_time = sum(r["time_ms"] for r in results) / total

    for r in results:
        status = "✅" if r["correct"] else "❌"
        print(f"  {status} {r['name']}: {r['time_ms']:.1f}ms")

    print(f"\n  Detection rate: {detected}/{total} ({detected/total*100:.0f}%)")
    print(f"  Fix accuracy:   {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"  Avg speed:      {avg_time:.1f}ms per case")
    all_results["unused_import"] = {
        "detection_rate": f"{detected}/{total}",
        "fix_accuracy": f"{correct}/{total}",
        "accuracy_pct": round(correct / total * 100),
        "avg_ms": round(avg_time, 1),
        "cases": results,
    }

    # ── Duplicate Var Agent ──
    print("\n📋 Duplicate Variable Agent")
    print("-" * 40)
    agent = DuplicateVarAgent()
    results = run_agent_test(agent, DUPLICATE_VAR_CASES)
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    detected = sum(1 for r in results if r["produced_edit"] == r["expected_change"])
    avg_time = sum(r["time_ms"] for r in results) / total

    for r in results:
        status = "✅" if r["correct"] else "❌"
        print(f"  {status} {r['name']}: {r['time_ms']:.1f}ms")

    print(f"\n  Detection rate: {detected}/{total} ({detected/total*100:.0f}%)")
    print(f"  Fix accuracy:   {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"  Avg speed:      {avg_time:.1f}ms per case")
    all_results["duplicate_var"] = {
        "detection_rate": f"{detected}/{total}",
        "fix_accuracy": f"{correct}/{total}",
        "accuracy_pct": round(correct / total * 100),
        "avg_ms": round(avg_time, 1),
        "cases": results,
    }

    # ── Missing Export Agent ──
    print("\n📋 Missing Export Agent")
    print("-" * 40)
    agent = MissingExportAgent()
    results = run_agent_test(agent, MISSING_EXPORT_CASES, uses_build_log=True)
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    detected = sum(1 for r in results if r["produced_edit"] == r["expected_change"])
    avg_time = sum(r["time_ms"] for r in results) / total

    for r in results:
        status = "✅" if r["correct"] else "❌"
        print(f"  {status} {r['name']}: {r['time_ms']:.1f}ms")

    print(f"\n  Detection rate: {detected}/{total} ({detected/total*100:.0f}%)")
    print(f"  Fix accuracy:   {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"  Avg speed:      {avg_time:.1f}ms per case")
    all_results["missing_export"] = {
        "detection_rate": f"{detected}/{total}",
        "fix_accuracy": f"{correct}/{total}",
        "accuracy_pct": round(correct / total * 100),
        "avg_ms": round(avg_time, 1),
        "cases": results,
    }

    # ── Export Spelling Agent ──
    print("\n📋 Export Spelling Agent")
    print("-" * 40)
    agent = ExportSpellingAgent()
    results = run_agent_test(agent, EXPORT_SPELLING_CASES, uses_build_log=True)
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    detected = sum(1 for r in results if r["produced_edit"] == r["expected_change"])
    avg_time = sum(r["time_ms"] for r in results) / total

    for r in results:
        status = "✅" if r["correct"] else "❌"
        print(f"  {status} {r['name']}: {r['time_ms']:.1f}ms")

    print(f"\n  Detection rate: {detected}/{total} ({detected/total*100:.0f}%)")
    print(f"  Fix accuracy:   {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"  Avg speed:      {avg_time:.1f}ms per case")
    all_results["export_spelling"] = {
        "detection_rate": f"{detected}/{total}",
        "fix_accuracy": f"{correct}/{total}",
        "accuracy_pct": round(correct / total * 100),
        "avg_ms": round(avg_time, 1),
        "cases": results,
    }

    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_cases = sum(len(v["cases"]) for v in all_results.values())
    total_correct = sum(sum(1 for c in v["cases"] if c["correct"]) for v in all_results.values())
    overall_pct = round(total_correct / total_cases * 100)

    print(f"\n  Overall fix accuracy: {total_correct}/{total_cases} ({overall_pct}%)")
    print(f"\n  Per-agent breakdown:")
    for agent_name, data in all_results.items():
        print(f"    {agent_name}: {data['fix_accuracy']} ({data['accuracy_pct']}%) @ {data['avg_ms']}ms avg")

    # Save results
    results_path = Path(__file__).parent / "results.json"
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Results saved to {results_path}")


if __name__ == "__main__":
    main()
