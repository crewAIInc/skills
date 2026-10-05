# What Each Deploy Path Uploads

Exactly what `crewai deploy create` / `crewai deploy push` send to CrewAI AMP on crewai 1.15.22-1.15.23, so a "successful" deploy never runs code or env values you did not expect.

---

## 1. Decision flow inside the CLI

`crewai deploy create`:

1. Runs pre-deploy validation (unless `--skip-validate`). If there is no lockfile it runs `crewai install` to create one, then validates again.
2. Prepares Git: if the directory is not a Git repo, runs `git init` and commits everything not ignored as "Initial crew" (adding `.env`, `.env.*`, `.venv/`, caches, `build/`, `dist/` to `.git/info/exclude` first). If `origin` exists, runs `git fetch`.
3. Reads every `KEY=VALUE` line from `./.env`.
4. With an `origin` remote: asks you to confirm the env var names and the remote URL (`-y` skips both prompts), then creates a Git-based deployment from the project name, the remote URL, and the env vars. No code leaves your machine.
5. Without `origin`: prints `No origin remote found. Deploying from a ZIP upload instead.`, confirms the env var names, and uploads a ZIP plus the env vars.

`crewai deploy push [--uuid <id>]`:

1. Validation and lockfile handling as above.
2. Looks the deployment up by `--uuid`, or by `[project].name` in the currently selected org.
3. If AMP reports the deployment is ZIP-based: builds a fresh ZIP and re-sends every key in `./.env`. There is no confirmation prompt on this path.
4. If AMP reports it is Git-based: asks AMP to redeploy. Nothing is uploaded and no env vars are sent; AMP pulls the repository.
5. Only if AMP does not report the type: falls back to the local view - `origin` present means a Git redeploy, no `origin` means a ZIP upload with `.env`.

Consequence: the source type is fixed at create time. Adding an `origin` to a ZIP deployment, or removing it from a Git deployment, does not change how `push` deploys it.

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
| `push`, ZIP-based deployment | All `.env` keys, no prompt |
| `push`, Git-based deployment | None |
| Any path with no `.env` file | None (prints `Error: .env not found.` and continues) |

Practices:

- Keep values bare in `.env`: no inline comments, no surrounding quotes.
- Keep only this deployment's keys in the project `.env`; never park unrelated secrets there.
- To redeploy a ZIP deployment without touching its variables, move `.env` aside for the push, and manage values in the dashboard.
- On a Git-based deployment, change env values in the dashboard; editing `.env` and pushing does nothing.
- Set every variable on the deployment itself and confirm it with a kickoff that reports the variable names it can see (never the values).

---

## 4. Dashboard paths

| Path | Notes |
|---|---|
| GitHub connection | Pick repository and branch; optional "Automatically deploy new commits". Env vars entered in the form. |
| ZIP upload | Upload a ZIP of the project root (not its parent folder). Exclude `.git`, `.venv`, `.env` and caches yourself. |
| Monorepo | Set a working directory (relative to the repo or ZIP root) in the dashboard. The CLI create flow has no option for it, and auto-deploy is disabled while a working directory is set. |

Docs: [Automations](https://docs.crewai.com/en/enterprise/features/automations), [Monorepo Deployments](https://docs.crewai.com/en/enterprise/guides/monorepo-deployments), [Deploy to AMP](https://docs.crewai.com/en/enterprise/guides/deploy-to-amp).
