# Releasing jyotirganita

Releases are published by `.github/workflows/release.yml` using **PyPI Trusted
Publishing** (OIDC). No API tokens are ever stored in this repository or in
GitHub Secrets — PyPI verifies the identity of the workflow run itself.

Two paths through the same workflow:

| Trigger | Target | GitHub environment |
| --- | --- | --- |
| Manual run (**Run workflow**) | TestPyPI | `testpypi` |
| Publishing a GitHub Release | PyPI | `pypi` |

Do the one-time setup once (steps 1–3), then repeat steps 4–5 for each release.

---

## 1. One-time: create the GitHub environments

Trusted Publishing is scoped to a GitHub *environment*, so both must exist
before the first run.

1. Go to <https://github.com/thomas-mathew-lab/jyotirganita/settings/environments>.
2. **New environment** → name it exactly `pypi` → **Configure environment** → save.
   (Optionally add yourself under *Required reviewers* so real PyPI uploads pause
   for your approval.)
3. **New environment** again → name it exactly `testpypi` → save. Leave this one
   without reviewers so dry runs are frictionless.

Names are case-sensitive and must match the workflow exactly.

## 2. One-time: register the pending publisher on PyPI

Because the project does not exist on PyPI yet, this is a *pending* publisher —
it becomes a normal trusted publisher the moment the first upload lands.

1. Sign in at <https://pypi.org> and enable 2FA if you have not
   (Account settings → *Two-factor authentication*).
2. Go to <https://pypi.org/manage/account/publishing/>.
3. Under **Add a new pending publisher**, choose the **GitHub** tab and fill in:
   - **PyPI Project Name:** `jyotirganita`
   - **Owner:** `thomas-mathew-lab`
   - **Repository name:** `jyotirganita`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi`
4. Click **Add**. It should now appear under *Pending publishers*.

## 3. One-time: register the pending publisher on TestPyPI

TestPyPI is a **separate site with a separate account** — your PyPI login does
not work there.

1. Register at <https://test.pypi.org/account/register/> and enable 2FA.
2. Go to <https://test.pypi.org/manage/account/publishing/>.
3. Add a pending publisher with the same values as above, except:
   - **Environment name:** `testpypi`
4. Click **Add**.

## 4. Dry run on TestPyPI

1. Confirm `version` in `pyproject.toml` is the version you intend to ship, and
   that it matches `__version__` in `jyotirganita/__init__.py` and `version:` in
   `CITATION.cff`.
2. Go to
   <https://github.com/thomas-mathew-lab/jyotirganita/actions/workflows/release.yml>.
3. Click **Run workflow** → branch `main` → **Run workflow**.
4. Watch both jobs go green. The `publish` job uploads to TestPyPI.
5. Verify the upload installs cleanly from a scratch virtualenv:

   ```bash
   python -m venv /tmp/jg && /tmp/jg/bin/pip install \
     --index-url https://test.pypi.org/simple/ jyotirganita
   /tmp/jg/bin/python -c "import jyotirganita; print(jyotirganita.__version__)"
   ```

   (`--index-url` alone is enough here: the package has no dependencies, so
   there is nothing to fall back to real PyPI for.)
6. Check the rendered project page at <https://test.pypi.org/project/jyotirganita/>
   — this is exactly how `README.md` will look on PyPI.

If anything is wrong, fix it and **bump the version**. A version number can
never be re-uploaded or reused on either site, even after deletion.

## 5. Cut the real release

1. Make sure `main` contains exactly what you want to publish.
2. Go to
   <https://github.com/thomas-mathew-lab/jyotirganita/releases/new>.
3. **Choose a tag** → type `v0.0.1` → **Create new tag: v0.0.1 on publish**.
4. Target: `main`. Release title: `v0.0.1`.
5. Write short release notes (for `0.0.1`: name reservation, no functionality).
6. Leave *Set as a pre-release* unchecked and click **Publish release**.
7. The workflow fires on `release: published`, builds, and uploads to real PyPI.
   If you added required reviewers to the `pypi` environment, approve the run
   when Actions prompts you.
8. Confirm <https://pypi.org/project/jyotirganita/0.0.1/> exists and that
   `pip install jyotirganita` works from a clean virtualenv.

---

## Later: the 1.0.0 release

Nothing about the pipeline changes — the pending publishers become permanent
after the first upload, and the same workflow handles every subsequent version.
For `1.0.0`:

1. Bump the version in `pyproject.toml`, `jyotirganita/__init__.py`
   (`__version__`), and `CITATION.cff` (`version:`).
2. Replace the placeholder notice in `README.md` with real documentation, and
   remove the module-level `__getattr__` stub from `jyotirganita/__init__.py`.
3. Update the `Development Status` classifier in `pyproject.toml`.
4. Run the TestPyPI dry run (step 4) to check the rendered page and metadata.
5. Publish a GitHub Release tagged `v1.0.0` (step 5).

Version numbers after `1.0.0` follow semantic versioning.

### Note on version strings

PyPI normalizes versions per [PEP 440](https://peps.python.org/pep-0440/):
`0.01` would normalize to `0.1`. Always write three-part versions —
`0.0.1`, `1.0.0` — so what you tag is what PyPI stores.

### Note on Zenodo

Do not connect Zenodo until after `0.0.1` is out. Enabling it now would mint a
permanent DOI for an empty placeholder. Turn it on after `0.0.1` and before
`v1.0.0` so the first archived DOI points at real software.
