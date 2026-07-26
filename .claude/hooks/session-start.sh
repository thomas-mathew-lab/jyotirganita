#!/bin/bash
# SessionStart hook: pin git authorship to Thomas Mathew.
#
# Claude Code on the web runs in an ephemeral container whose git identity
# defaults to "Claude <noreply@anthropic.com>". That would misrepresent
# authorship on a public academic project, so re-apply the correct identity at
# the start of every session. Idempotent and non-interactive.
set -euo pipefail

# Local checkouts already have a real human identity configured; leave it alone.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$(dirname "$(dirname "$(realpath "$0")")")")}"

# Never rewrite authorship in someone else's fork.
origin="$(git remote get-url origin 2>/dev/null || true)"
case "$origin" in
  *thomas-mathew-lab/jyotirganita*) ;;
  *)
    echo "session-start: origin is not thomas-mathew-lab/jyotirganita; leaving git identity unchanged." >&2
    exit 0
    ;;
esac

git config user.name  "Thomas Mathew"
git config user.email "69473504+mathew-physics@users.noreply.github.com"

echo "session-start: git identity set to $(git config user.name) <$(git config user.email)>"
