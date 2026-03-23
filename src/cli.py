#!/usr/bin/env python3
"""
build-fix CLI

Usage:
  build-fix [PROJECT_ROOT] [--log build.log] [--cmd "npm run build"] [--no-verify]

Examples:
  build-fix .
  build-fix ./my-app --log build.log
  build-fix ./my-app --cmd "pnpm build" --no-verify
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="build-fix",
        description="Auto-repair TypeScript/JS build errors: duplicates, missing exports, spelling, unused imports.",
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        help="Path to project root (default: current directory)",
    )
    parser.add_argument(
        "--log",
        metavar="FILE",
        help="Path to a captured build log file (improves accuracy)",
    )
    parser.add_argument(
        "--cmd",
        metavar="CMD",
        default="npm run build",
        help="Build command to verify fixes (default: npm run build)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Apply fixes without running build verification",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    build_log = None
    if args.log:
        log_path = Path(args.log)
        if not log_path.exists():
            print(f"Warning: log file {log_path} not found, continuing without it", file=sys.stderr)
        else:
            build_log = log_path.read_text(encoding="utf-8", errors="replace")

    # Import here so CLI startup is fast
    from build_fix.fixer import apply_build_fix

    print(f"Scanning {root} ...")
    result = apply_build_fix(
        project_root=root,
        build_log=build_log,
        build_cmd=args.cmd,
        verify=not args.no_verify,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["success"] else 1)

    # Human-readable output
    status = "✅" if result["success"] else "❌"
    print(f"\n{status} {result['message']}")

    if result.get("applied_edits"):
        print("\nApplied fixes:")
        for e in result["applied_edits"]:
            print(f"  • {e['file_path']}: {e['description']}")

    if result.get("reverted"):
        print("\n⚠️  All changes were reverted.")
    if result.get("build_verified"):
        print("✅ Build verified successfully.")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
