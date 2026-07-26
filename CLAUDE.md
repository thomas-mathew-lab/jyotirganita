# Conventions for this repository

## Commit attribution

Thomas Mathew is the git **author** of every commit here. Before committing, set
the repository identity:

```bash
git config user.name  "Thomas Mathew"
git config user.email "69473504+mathew-physics@users.noreply.github.com"
```

`.claude/settings.json` registers a `SessionStart` hook that does this
automatically, since web session containers are ephemeral and otherwise default
to `Claude <noreply@anthropic.com>`. Verify with
`git log --format='%an <%ae>'` and amend any commit that shows otherwise.

**Keep** the `Co-Authored-By: Claude <noreply@anthropic.com>` trailer, naming
whichever model produced the work. AI assistance is disclosed accurately; it is
not passed off as sole human authorship, and not passed off as authorship of the
work either.

## Versioning

- `0.0.1` is a placeholder release that reserves the package name on PyPI. It
  contains no functionality.
- `1.0.0` will be the first real public release.
- Semantic versioning applies from `1.0.0` onward.

Always write three-part version numbers. PyPI normalizes per PEP 440, so `0.01`
would become `0.1`. A version can never be re-uploaded or reused once published.
Keep `pyproject.toml`, `jyotirganita/__init__.py` (`__version__`), and
`CITATION.cff` (`version:`) in agreement.

## History

Changes are committed here as self-contained snapshots. Never merge, fork, or
import history from another repository into this one.
