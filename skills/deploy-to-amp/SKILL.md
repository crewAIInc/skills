---
name: deploy-to-amp
description: "Getting a CrewAI crew or flow onto CrewAI AMP: the project shape the build expects (uv.lock, [tool.crewai] type, src/<pkg>/ entry points, a real Flow subclass, absolute imports, a self-contained root), `crewai deploy validate`, the three deploy paths (CLI create/push, GitHub, ZIP upload) and what each one actually uploads, env vars per deployment and what the CLI re-sends from .env, provider keys and extras, and machine-wide org selection. Use when running `crewai deploy create` / `crewai deploy push` / `crewai deploy validate`, when a deploy says Online but runs old code or old env values, or when pasting errors like `missing_lockfile`, `Crew class annotated with @CrewBase not found`, `No Flow subclass found`, `Expected to find at least one of these files: uv.lock or poetry.lock`, `OPENAI_API_KEY is required`, `Anthropic native provider not available`, `deployment_not_found`, or `pyproject.toml not found`."
---

# Deploy to CrewAI AMP

Ship a crew or flow to AMP without burning deploys on project-shape errors, stale code, stale env values, or the wrong org.

Verified against crewai 1.15.22 and 1.15.23 on 2026-10-01.
Run `crewai version` first; if the major/minor differs, re-verify the version-sensitive rows below with the `ask-docs` skill before trusting them.

Where the getting-started, design-agent or design-task skills in this plugin disagree with this skill, follow this skill - it was re-checked against crewai 1.15.22 and 1.15.23. The installed crewai source outranks both.

---

## 1. Preflight - run these three every time

```bash
crewai org current        # which org will receive this deploy (machine-wide, see section 5)
uv lock && git status     # lockfile fresh, and you know what is uncommitted
crewai deploy validate    # local checks, no platform contact, exit 1 on blocking errors
```

`crewai deploy create` and `crewai deploy push` run the same validation automatically (skip with `--skip-validate` only when you know why). Every `crewai deploy` subcommand must run from the project root - elsewhere it stops with `Error: pyproject.toml not found.`

---

## 2. Project shape the build expects

| Requirement | Crew (classic, `crewai create crew <name> --classic`) | Flow (`crewai create flow <name>`) |
|---|---|---|
| `[tool.crewai] type` | `"crew"` | `"flow"` |
| Lockfile | `uv.lock` (or `poetry.lock`) at the root, committed | same |
| Package dir | `src/<pkg>/`, where `<pkg>` is `[project].name` normalized (`research-crew` -> `research_crew`) | same |
| Entry code | `src/<pkg>/crew.py` with an `@CrewBase` class, plus `config/agents.yaml` and `config/tasks.yaml` | `src/<pkg>/main.py` with a `Flow` subclass that can be built with no arguments, plus `kickoff()` |
| Scripts (scaffold) | `run_crew = "<pkg>.main:run"` | `kickoff = "<pkg>.main:kickoff"` |
| Imports | absolute: `from research_crew.tools.x import Y` | absolute: `from acme_flow.crews.content_crew.content_crew import ContentCrew` |

JSON-first crews (plain `crewai create crew <name>`, no `--classic`) keep `crew.jsonc` and `agents/` at the project root instead of `src/`; `crewai deploy validate` checks that layout too.

Minimal flow `main.py` that passes validation:

```python
from crewai.flow import Flow, listen, start
from pydantic import BaseModel


class ReportState(BaseModel):
    topic: str = "AI agents"
    summary: str = ""


class ReportFlow(Flow[ReportState]):
    @start()
    def gather(self):
        return f"notes on {self.state.topic}"

    @listen(gather)
    def summarize(self, notes):
        self.state.summary = notes.upper()
        return self.state.summary


def kickoff():
    ReportFlow().kickoff()


if __name__ == "__main__":
    kickoff()
```

### Shape rules, each with the failure it prevents

| Bad | What happens | Good |
|---|---|---|
| `from .stub_tools import X` in `crew.py` / `main.py` | `crewai run` works, but `crewai deploy validate` fails with `Crew class annotated with @CrewBase not found` (the loader runs the file outside its package, and the real `attempted relative import` error is hidden) | `from research_crew.stub_tools import X` |
| Only a `def kickoff():` in `main.py`, no Flow class | `No Flow subclass found in the module` | Define `class MyFlow(Flow[...])` and call it from `kickoff()` |
| Flow `__init__(self, tenant: str)` | `No Flow subclass found` - the class must build with no arguments | Pass per-run values through `kickoff(inputs={...})` into state |
| `type = "flow"` on a crew project | `No Flow subclass found` | `type = "crew"` |
| `type = "crew"` on a flow project | `Cannot find src/<pkg>/crew.py`, `Cannot find src/<pkg>/config` | `type = "flow"` |
| Renamed `src/research_crew/` to `src/researchcrew/` | `Cannot find src/research_crew/` and `Hatchling cannot determine which files to ship` | Keep the dir equal to the normalized `[project].name` |
| `uv.lock` missing | `missing_lockfile` error | `uv lock`, then `git add uv.lock` |
| Edited `pyproject.toml` after locking | `stale_lockfile` warning (does not block) - deployed deps may differ from local | Re-run `uv lock` after every `pyproject.toml` edit and commit both |
| Importing code from a sibling dir (`../shared_lib`) via `sys.path` | Validate passes locally, but only the project root is uploaded, so the import fails on AMP | Move shared code inside `src/<pkg>/` or publish it as a package dependency |
| `anthropic/...` model with plain `crewai[tools]` | `Anthropic native provider not available, to install: uv add "crewai[anthropic]"` - validate reports it only as `@CrewBase not found` | `uv add "crewai[anthropic]"` so the extra lands in `pyproject.toml` and `uv.lock` |

Keep data files inside `src/<pkg>/` and load them as package data, not with paths built from the repo root. Files under `src/<pkg>/` go into the wheel the scaffold builds; files at the project root do not.

```python
from importlib.resources import files

rules = files("research_crew").joinpath("data/rules.json").read_text()
```

When validate says `@CrewBase not found` or `No Flow subclass found` and the class is clearly there, the loader swallowed the real error. Reproduce it with a traceback:

```bash
# 1. Run the file outside its package, as the loader does (catches relative imports and import-time errors)
uv run python -c "import runpy; runpy.run_path('src/research_crew/crew.py', run_name='deploy_check')"   # flows: src/<pkg>/main.py
# 2. Build the object with no arguments (catches missing provider extras and Flow `__init__` arguments)
uv run python -c "from research_crew.crew import ResearchCrew; ResearchCrew().crew()"
uv run python -c "from acme_flow.main import ContentFlow; ContentFlow()"
```

See [validate-checks.md](references/validate-checks.md) for every check and code.

---

## 3. The three deploy paths and what each one uploads

| Path | Code AMP builds | Env vars sent |
|---|---|---|
| `crewai deploy create`, project has an `origin` remote | AMP clones the repo; nothing is uploaded from your disk | Every key in local `.env`, after a "Press Enter to continue with N env vars: ..." prompt (`-y` skips it) |
| `crewai deploy create`, no `origin` remote | A ZIP of your working tree (prints `No origin remote found. Deploying from a ZIP upload instead.`) | Every key in local `.env`, after the same prompt |
| `crewai deploy push` on a Git-based deployment | AMP rebuilds from the repository - your uncommitted and unpushed changes are not included | None |
| `crewai deploy push` on a ZIP-based deployment | A fresh ZIP of your working tree, including uncommitted edits | Every key in local `.env`, re-sent with no prompt |
| Dashboard, GitHub connection | The repository and branch you pick (optional auto-deploy on new commits) | What you enter in the dashboard |
| Dashboard, ZIP upload | The ZIP you choose | What you enter in the dashboard |

Rules that follow from this:

- A deployment keeps the source it was created with. `push` asks AMP which kind it is, so adding or removing a local `origin` later does not switch a Git deployment to ZIP or back.
- Git-based: `git commit` and `git push` before `crewai deploy push`, or the build runs your last pushed code.
- ZIP-based: the ZIP holds files Git tracks plus untracked files that are not ignored, and always drops `.env`, `.env.*` (except `.env.example` / `.env.sample`), `.git`, `.venv`, caches, `build/` and `dist/`. Add run outputs (`report.md`, `output/`) and scratch files to `.gitignore`, or they ship.
- If the directory is not a Git repo yet, `create`/`push` runs `git init` and commits everything not ignored as "Initial crew". If `uv.lock` is missing they run `crewai install` to create it.
- Only the project root is packaged. Monorepo subfolders need a working directory set in the dashboard (the CLI create flow has no such option).
- `push` without `--uuid` finds the deployment by `[project].name` in the selected org. Keep the name stable, or pass `--uuid`.
- `crewai deploy logs` fetches the deployment (build) log. Read run output from the kickoff result or the dashboard's Executions and Traces tabs.
- "Online" means the build finished. After every deploy, kick off the cheapest real input and read the output (see `call-deployed-crew`).

Full matrix, exclusions, and a script to list what a ZIP deploy would contain: [what-gets-uploaded.md](references/what-gets-uploaded.md).

---

## 4. Environment variables

Env vars live on each deployment. Set provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...) and tool keys (`SERPER_API_KEY`, ...) as that deployment's environment variables in the AMP dashboard, and confirm them with a kickoff rather than assuming an org-level setting reaches your code.

What the CLI does with local `.env`:

| Situation | What gets sent |
|---|---|
| `.env` present on `create`, or on `push` to a ZIP deployment | Every non-comment `KEY=VALUE` line, unfiltered - including unrelated secrets in the file |
| `.env` absent | No env fields at all (it prints `Error: .env not found.` and carries on) |
| `push` to a Git deployment | Never sends env vars - change values in the dashboard |

Values are sent verbatim: `MAX_CASES=3  # note` arrives as `3  # note`, and `QUOTED="abc"` arrives with the quotes. Write `.env` with bare values and no inline comments.

To push code without touching a ZIP deployment's variables, run `crewai deploy push` from a tree with no `.env` (move it aside) and manage values in the dashboard. Ship a `.env.example` with `<your-key>` placeholders so the required names are documented.

Provider facts that bite on deploy:

- An agent with no `llm=` uses the OpenAI default (`gpt-4.1-mini`), so it needs `OPENAI_API_KEY` even in an Anthropic-only project. Set `llm=` on every agent.
- The OpenAI provider reads its key from `api_key=` or `OPENAI_API_KEY`; the error at kickoff is `ValueError: OPENAI_API_KEY is required`.
- Non-OpenAI providers are extras: `crewai[anthropic]`, `crewai[google-genai]`, `crewai[bedrock]`, `crewai[azure-ai-inference]`. Add them with `uv add` so they are in `pyproject.toml` and `uv.lock`; a locally `pip install`ed SDK is invisible to the build.
- `crewai deploy validate` warns (`env_vars_not_in_dotenv`) when code calls `os.getenv("SERPER_API_KEY")` or similar for a known key that is missing from `.env` and your shell. It is a reminder to add the key to the deployment, not a blocker.

---

## 5. Org selection is machine-wide

The CLI keeps one selected org per OS user in `~/.config/crewai/settings.json`, and every platform call (`deploy create/push/status/logs/list/remove`) carries that org. Switching in one terminal switches it for every shell and project on the machine.

- Run `crewai org current` before every create, push, or remove. (Bare `crewai org` prints nothing on 1.15.22-1.15.23 - use the `current` subcommand.)
- `crewai org list` shows the orgs you belong to; `crewai org switch <org-id>` changes the selection.
- `crewai login` replaces the selection with the account's current org as reported by the platform, so re-check with `crewai org current` after every login.
- A "not found" from `deploy push/status/logs` (including `deployment_not_found`) usually means the CLI is pointed at a different org than the one that owns the deployment. Check the org before debugging the deployment.
- Scripts and CI that drive the CLI should switch org explicitly at the start and verify it, never rely on whatever was last selected.

---

## 6. Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| Deploy is Online but runs old code | Git-based deployment and the change was not pushed | `git push`, then `crewai deploy push` |
| Deploy keeps old env values after editing `.env` | Git-based push never sends env vars | Edit the values in the dashboard |
| A stale value overwrites a rotated key, or an unrelated secret appears on the deployment | ZIP `create`/`push` uploaded every key in local `.env` | Deploy from a tree without `.env`; keep only deployment keys in it |
| `MAX_CASES` parses as `3  # note` | Inline comment in `.env` sent verbatim | Bare values only |
| `Expected to find at least one of these files: uv.lock or poetry.lock` | No lockfile | `uv lock`, commit it |
| Validate passed on the second run although you never ran `uv lock` | Validate's import check ran `uv run`, which created `uv.lock` | Commit the new `uv.lock` (a Git-based build only sees committed files) |
| `Crew class annotated with @CrewBase not found` with the decorator present | Relative import, missing provider extra, or any import error in `crew.py` | Run the diagnostic commands in section 2 to see the real error |
| `No Flow subclass found in the module` | No Flow class, Flow needs constructor args, or `type = "flow"` on a crew | Add a no-arg Flow subclass; fix `type` |
| `ImportError` on AMP for code that works locally | Imports from outside the project root | Move it under `src/<pkg>/` or make it a dependency |
| `Anthropic native provider not available` | Extra missing from `pyproject.toml` | `uv add "crewai[anthropic]"` |
| `ValueError: OPENAI_API_KEY is required` at kickoff | Agent without `llm=` or OpenAI model and no key on the deployment | Set `llm=` explicitly; add the key as a deployment env var |
| `deployment_not_found` / not found on push or status | Wrong org selected | `crewai org current`, then `crewai org switch <org-id>` |
| `Error: pyproject.toml not found.` from `crewai deploy list` | Run outside a project dir | `cd` to the project root |
| Deployment from a monorepo subfolder fails to find the project | Only the repo or ZIP root is used by default | Set the working directory in the dashboard |

---

## 7. Deploy checklist

- [ ] `crewai org current` shows the intended org
- [ ] `[tool.crewai] type` matches the project (crew or flow)
- [ ] `src/<pkg>/` matches `[project].name`; crew has `@CrewBase` + `config/*.yaml`, flow has a no-arg `Flow` subclass + `kickoff()`
- [ ] All project imports are absolute; nothing imported from outside the project root
- [ ] Provider extras (`crewai[anthropic]`, ...) added with `uv add`; `uv lock` run after the last `pyproject.toml` edit
- [ ] `uv.lock` committed
- [ ] `crewai deploy validate` exits 0
- [ ] Git-based: changes committed and pushed. ZIP-based: run outputs and scratch files ignored
- [ ] `.env` holds only this deployment's keys with bare values - or is moved aside so nothing is sent
- [ ] Provider and tool keys set as the deployment's env vars in the dashboard
- [ ] After Online, one cheap kickoff returned the expected output

---

## References

- [What gets uploaded](references/what-gets-uploaded.md) - per-path matrix, ZIP include/exclude rules, env-var handling, and a script to list what a ZIP deploy would contain
- [Validate checks](references/validate-checks.md) - every `crewai deploy validate` check, its code and severity, and what it cannot catch
- Public docs: [Prepare for Deployment](https://docs.crewai.com/en/enterprise/guides/prepare-for-deployment), [Deploy to AMP](https://docs.crewai.com/en/enterprise/guides/deploy-to-amp), [Automations](https://docs.crewai.com/en/enterprise/features/automations), [Monorepo Deployments](https://docs.crewai.com/en/enterprise/guides/monorepo-deployments), [CLI](https://docs.crewai.com/en/concepts/cli)

For related skills:

- **call-deployed-crew** - `/inputs`, `/kickoff`, `/status` once the deployment is Online
- **test-crewai-project** - offline stub LLM so `crewai run` and validate work without keys
- **check-crewai-api** - current `LLM` model strings, default model, structured output
- **build-flow** - Flow state, routers, persistence
- **connect-tools-and-mcp** - which tool and MCP transports work on a hosted deployment
- **ask-docs** - query the live docs for anything not covered here
