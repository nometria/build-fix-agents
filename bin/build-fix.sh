#!/usr/bin/env bash
# npx build-fix wrapper — installs the Python package and forwards all args.
#
# Usage:
#   npx build-fix .
#   npx build-fix ./my-app --log build.log --cmd "pnpm build"

set -euo pipefail

# Check for Python 3
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not found. Install Python 3.9+ first." >&2
  exit 1
fi

# Check minimum Python version (3.9)
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  echo "Error: Python 3.9+ is required (found $PY_VERSION)." >&2
  exit 1
fi

# Install build-fix if not already available
if ! python3 -m build_fix --help &>/dev/null 2>&1 && ! command -v build-fix &>/dev/null; then
  echo "Installing build-fix..." >&2
  pip install build-fix --quiet 2>/dev/null || python3 -m pip install build-fix --quiet
fi

# Run build-fix with all forwarded arguments
exec build-fix "$@"
