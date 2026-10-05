# What Each Deploy Path Uploads

Exactly what `crewai deploy create` / `crewai deploy push` send to CrewAI AMP on crewai 1.15.22-1.15.23, so a "successful" deploy never runs code or env values you did not expect.

---

## 1. Decision flow inside the CLI

`crewai deploy create`:

1. Runs pre-deploy validation (unless `--skip-validate`). If there is no lockfile it ignores `missing_lockfile`, and validation's own `uv run` usually creates `uv.lock`; if it is still missing, it runs `crewai install`, then validates again.
2. Prepares Git: if the directory is not a Git repo, runs `git init`; if the repo has no commits (the `crewai create` scaffold runs `git init` without committing), commits everything not ignored as "Initial crew" after adding `.env`, `.env.*`, `.venv/`, caches, `build/`, `dist/` to `.git/info/exclude`. If `origin` exists, runs `git fetch`.
3. Reads every `KEY=VALUE` line from `./.env`.
4. With an `origin` remote: asks you to confirm the env var names and the remote URL (`-y` skips both prompts), then creates a Git-based deployment from the project name, the remote URL, and the env vars. No code leaves your machine. The CLI does not check that AMP can read the repo: with a private repo AMP has no access to, create succeeds and the build fails with `git_clone_failure` (`fatal: could not read Username for 'https://github.com': terminal prompts disabled`).
5. Without `origin`: prints `No origin remote found. Deploying from a ZIP upload instead.`, shows `Press Enter to continue with N env vars: KEY1, KEY2` (`-y` skips it; with no terminal input it aborts before uploading), and uploads a ZIP plus the env vars.

`crewai deploy push [--uuid <id>]`:

1. Validation and lockfile handling as above.
2. Looks the deployment up by `--uuid`, or by `[project].name` in the currently selected org.
3. If the status response carries the CLI's ZIP flag, it follows it: ZIP-based means a fresh ZIP plus every key in `./.env`; Git-based means a redeploy request.
4. Otherwise it falls back to the local view - `origin` present means a redeploy request (nothing uploaded, no env vars), no `origin` means a ZIP upload with `.env` and no confirmation prompt.

On crewai 1.15.22-1.15.23, `push` takes step 4 in practice. AMP itself builds from the source chosen at create time. Observed live:

| Deployment | Local state at `push` | CLI did | AMP did |
|---|---|---|---|
| ZIP | no `origin` | ZIP of the working tree (uncommitted edit included) + `.env` | Built the new ZIP; the uncommitted code ran |
| ZIP | `origin` added later | Redeploy request only | Rebuilt the previous ZIP; new code and `.env` values were not deployed; Online |
| Git | `origin` present | Redeploy request only | Cloned the repository |
| Git | `origin` removed | ZIP + `.env` | Ignored the ZIP and cloned the repository |

Consequence: never change `origin` after create, and read the push output - `Preparing project ZIP...` / `Uploading project ZIP...` appear only when a ZIP was sent. `push` also prints the deployment record, including its bearer token; keep that output out of tickets and CI logs.

---

## 2. What goes into the ZIP

| Included | Excluded |
|---|---|
| Files Git tracks, in their current working-tree state (uncommitted edits included) | Anything matched by `.gitignore` |
| Untracked files that are not ignored (run outputs, notes, scratch data) | `.env`, and `.env.*` except `.env.example` and `.env.sample` |
| `.env.example`, `.env.sample` | `.git/`, `.venv/`, `venv/`, `env/`, `.crewai/`, `build/`, `dist/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.tox/` |
| | `.DS_Store`, `*.pyc`, `*.pyo`, symlinks |
| | Everything outside the project root |

Without Git available at all, the CLI walks the directory instead and `.gitignore` is not applied - only the fixed exclusions above.

Root-level dotfiles (`.gitignore`, `.env.example`) ship in the ZIP but may not be present in the running deployment's root; do not depend on them at runtime.

Preview the file list before a ZIP deploy (matches the CLI's selection exactly on 1.15.22-1.15.23 in a Git checkout):

```bash
git ls-files --cached --others --exclude-standard \
  | grep -Ev '(^|/)(\.crewai|\.git|\.venv|venv|env|build|dist|__pycache__|\.mypy_cache|\.pytest_cache|\.ruff_cache|\.tox)/' \
  | awk -F/ '{n=$NF} n==".env"||n==".DS_Store"||n~/\.py[co]$/ {next}
             n~/^\.env\./ && n!=".env.example" && n!=".env.sample" {next} {print}'
```

If anything in that list should not ship (customer data, `report.md`, `output/`, notebooks), add it to `.gitignore` or deploy from a pruned copy of the project that holds only what ships.

---

## 3. Env vars the CLI sends

The `.env` reader is literal:

| `.env` line | Value sent |
|---|---|
| `OPENAI_API_KEY=<your-key>` | `<your-key>` |
| `MAX_CASES=3  # note` | `3  # note` |
| `QUOTED="abc"` | `"abc"` (quotes included) |
| `# comment` / blank line | skipped |
| Any other key in the file | sent too - there is no filtering by what the code uses |

| Command and path | Env vars sent |
|---|---|
| `create` (Git or ZIP) | All `.env` keys |
| `push` with no local `origin` (ZIP) | All `.env` keys, no prompt - **replacing** the deployment's variables: keys absent from `.env` are deleted |
| `push` with a local `origin` | None |
| Any path with no `.env` file | None (prints `Error: .env not found.` and continues); existing deployment variables are kept |

Example: pushing a `.env` that lacks `ANTHROPIC_API_KEY` removes it from the deployment; status stays `Crew is Online` and the next kickoff fails with `ValueError: ANTHROPIC_API_KEY is required`.

Practices:

- Keep values bare in `.env`: no inline comments, no surrounding quotes.
- Keep exactly this deployment's complete key set in the project `.env`; never park unrelated secrets there, and never push with a partial file.
- To redeploy a ZIP deployment without touching its variables, move `.env` aside for the push, and manage values in the dashboard.
- On a Git-based deployment, change env values in the dashboard; editing `.env` and pushing does nothing.
- Locally, python-dotenv strips inline comments (`3  # note` -> `3`), so a local run will not reveal the verbatim value the deployment receives.
- Set every variable on the deployment itself and confirm it with a kickoff that reports the variable names it can see (never the values).

---

## 4. Dashboard paths

| Path | Notes |
|---|---|
| GitHub connection | Pick repository and branch; optional "Automatically deploy new commits". Env vars entered in the form. |
| ZIP upload | Upload a ZIP of the project root (not its parent folder). Exclude `.git`, `.venv`, `.env` and caches yourself. |
| Monorepo | Set a working directory (relative to the repo or ZIP root) in the dashboard. The CLI create flow has no option for it, and auto-deploy is disabled while a working directory is set. |

Docs: [Automations](https://docs-platform.crewai.com/platform/en/features/automations), [Monorepo Deployments](https://docs-platform.crewai.com/platform/en/guides/monorepo-deployments), [Deploy to AMP](https://docs-platform.crewai.com/platform/en/guides/deploy-to-amp).
