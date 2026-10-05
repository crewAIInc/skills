# `crewai deploy validate` Checks

Every check the local pre-deploy validator runs on crewai 1.15.22-1.15.23, the code it prints, and the gaps it leaves.

`crewai deploy validate` contacts no platform API. It exits 1 when any ERROR is found and 0 otherwise (warnings never block). `crewai deploy create` and `crewai deploy push` run the same checks first, but exit 0 when they stop on a validation error - gate scripts on `crewai deploy validate`.

The AMP build runs its own import test ("Testing automation..." in `crewai deploy logs`), so a project pushed with `--skip-validate` that has a relative import or an outside-the-root import fails there with the real traceback in the deployment log. The console output strips the bracketed code, so `ERROR [missing_lockfile] ...` prints as `ERROR  Expected to find ...` - match on the message text below.

---

## 1. Classic crew and Flow projects

Checks run in this order; a failure early on skips the checks that depend on it.

| Code | Severity | Message | Fix |
|---|---|---|---|
| `missing_pyproject` | ERROR | Cannot find pyproject.toml | Run from the project root |
| `invalid_pyproject` | ERROR | pyproject.toml is not valid TOML | Fix the TOML |
| `missing_project_name` | ERROR | pyproject.toml is missing [project].name | Add `name = "..."` under `[project]` |
| `missing_lockfile` | ERROR | Expected to find at least one of these files: uv.lock or poetry.lock | `uv lock` and commit it |
| `stale_lockfile` | WARNING | uv.lock is older than pyproject.toml | `uv lock` and commit. The check compares file times and `uv lock` does not rewrite a current lockfile; if `uv lock --check` passes, `touch uv.lock` |
| `missing_src_dir` | ERROR | Missing src/ directory | Use the `src/<pkg>/` layout |
| `missing_package_dir` | ERROR | Cannot find src/<pkg>/ | Make the dir match the normalized `[project].name` |
| `stale_egg_info` | WARNING | Stale build artifact in src/ | Delete `src/*.egg-info`, ignore it in Git |
| `missing_crew_py` | ERROR | Cannot find src/<pkg>/crew.py (crew type only) | Add `crew.py`, or set `type = "flow"` |
| `missing_config_dir`, `missing_agents_yaml`, `missing_tasks_yaml` | ERROR | Cannot find src/<pkg>/config... (crew type only) | Add `config/agents.yaml` and `config/tasks.yaml` |
| `missing_flow_main` | ERROR | Cannot find src/<pkg>/main.py (flow type only) | Add `main.py` with a Flow subclass |
| `hatch_wheel_target_missing` | ERROR | Hatchling cannot determine which files to ship | Fix the package dir, or add `[tool.hatch.build.targets.wheel] packages = ["src/<pkg>"]` |
| `no_crewbase_class` | ERROR | Crew class annotated with @CrewBase not found | See section 3 - often an import error in disguise |
| `no_flow_subclass` | ERROR | No Flow subclass found in the module | Add a Flow subclass that builds with no arguments |
| `missing_provider_extra` | ERROR | <Provider> provider extra not installed | `uv add "crewai[<extra>]"` |
| `llm_init_missing_key` | WARNING | LLM is constructed at import time but <KEY> is not set | Add the key to the deployment env vars |
| `llm_provider_init_failed` | ERROR | LLM native provider failed to initialize | Check the model string and extras |
| `env_var_read_at_import` | WARNING | <KEY> is read at import time via os.environ[...] | Use `os.getenv` inside methods, or set the deployment var |
| `stale_crewai_pin` | ERROR | Your lockfile pins a crewai version missing `_load_response_format` | `uv lock --upgrade-package crewai` |
| `pydantic_validation_error` | ERROR | Pydantic validation failed while loading your crew | Fix agent/task fields; `crewai run` shows the traceback |
| `import_failed` | ERROR | Could not import your crew/flow module | `crewai run` locally to reproduce |
| `import_timeout` | ERROR | Importing your crew/flow module timed out after 120s | Move network calls or heavy work out of module import |
| `uv_not_found` | WARNING | Skipping import check: `uv` not installed | Install uv |
| `env_vars_not_in_dotenv` | WARNING | N referenced API key(s) not in .env | Add the keys to the deployment's env vars |
| `old_crewai_pin` | WARNING | Lockfile pins crewai==X (older than 1.13.0) | `uv lock --upgrade-package crewai` |

The import check runs `uv run python ...` in the project, so it uses the project's own environment and lockfile. A side effect: if `uv.lock` was missing, the first validate run reports `missing_lockfile` and its own `uv run` creates `uv.lock`, so the second run passes. Commit that file.

`env_vars_not_in_dotenv` only knows common key names (OpenAI, Anthropic, Google/Gemini, Azure, AWS, Cohere, Groq, Mistral, Tavily, Serper, Serply, Perplexity, DeepSeek, OpenRouter, Firecrawl, Exa, Browserbase) and only sees `os.getenv("X")`, `os.environ["X"]`, `os.environ.get("X")` and `${X}` in YAML. A key in your shell environment also silences it.

---

## 2. JSON-first crew projects

When `[tool.crewai]` has `type = "crew"` and a `definition` (for example `crew.jsonc`), validate runs a JSON suite instead: pyproject and lockfile checks, `invalid_crew_definition`, `missing_agents_dir`, `invalid_crew_json`, `json_validation_environment_failed`, `env_vars_not_in_dotenv`, and the crewai pin check.

---

## 3. When the message hides the cause

`no_crewbase_class` and `no_flow_subclass` are raised whenever the loader finds zero crews or flows. The loader runs `crew.py` / `main.py` as a standalone module (outside its package) and swallows exceptions, so these all produce the same message:

| Real cause | Real error |
|---|---|
| Relative import in `crew.py` / `main.py` | `ImportError: attempted relative import with no known parent package` |
| Provider extra missing | `ImportError: Anthropic native provider not available, to install: uv add "crewai[anthropic]"` |
| Flow class needs constructor arguments | `TypeError: ...__init__() missing 1 required positional argument` |
| No Flow subclass at all | (nothing to show - add one) |

Reproduce the hidden error with a traceback:

```bash
# Run the file outside its package, as the loader does
uv run python -c "import runpy; runpy.run_path('src/research_crew/crew.py', run_name='deploy_check')"
uv run python -c "import runpy; runpy.run_path('src/acme_flow/main.py', run_name='deploy_check')"
# Build the object with no arguments, as the loader does
uv run python -c "from research_crew.crew import ResearchCrew; ResearchCrew().crew()"
uv run python -c "from acme_flow.main import ContentFlow; ContentFlow()"
```

`run_name='deploy_check'` keeps the `if __name__ == "__main__":` block from kicking the crew or flow off. All four exit 0 with no output on a healthy project.

---

## 4. What validate cannot catch

| Gap | Why | Defence |
|---|---|---|
| Imports from outside the project root | The local `sys.path` hack works; only the root is uploaded. On AMP the build's import test fails: `ModuleNotFoundError: No module named '<module>'`, status `Automation error, fix the code and deploy again.` | Keep each deployable self-contained |
| `origin` added or removed after create | Validate never looks at the deployment | Keep `origin` as it was at create; check push output for `Uploading project ZIP...` |
| AMP cannot read a private Git repo | Validate never contacts the platform | Connect the repo in the AMP org (Settings > Git Repositories) first; the failure shows only after create as `git_clone_failure` |
| Uncommitted or unpushed changes on a Git-based deployment | Validate reads your working tree; AMP builds from the repo | `git status` clean and pushed before `deploy push` |
| Wrong org selected | Validate never contacts the platform | `crewai org current` |
| Env var present locally but missing on the deployment | Validate reads local `.env` and your shell | Set it on the deployment; check with a kickoff |
| Runtime failures (bad model name, tool errors) | Validate only imports and constructs | One cheap kickoff after every deploy |
