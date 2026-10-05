---
name: ask-docs
description: "Query the official CrewAI documentation for answers. Use when the user has a CrewAI question that isn't fully covered by the other CrewAI skills in this plugin — e.g., specific API details, configuration options, advanced features, troubleshooting errors, enterprise features, tool references, or anything where the latest docs are the best source of truth."
---

# Ask CrewAI Docs

Answer CrewAI questions from the official documentation, matched to the crewai version the user actually runs.

Verified against crewai 1.15.23 and the docs sites below on 2026-10-01.
Live-tested with real LLMs on 2026-10-01.

There are two documentation sites:

| Site | Covers | Index | MCP server |
|---|---|---|---|
| `docs.crewai.com` | The open-source framework: agents, crews, tasks, flows, memory, knowledge, LLMs, tools, CLI, testing, telemetry, observability, and the AMP REST API reference (`/inputs`, `/kickoff`, `/status`, `/resume`) | `https://docs.crewai.com/llms.txt` | `https://docs.crewai.com/mcp` |
| `docs-platform.crewai.com` | CrewAI AMP (the hosted platform): deploying, automations, triggers, RBAC, secrets, Studio, platform API | `https://docs-platform.crewai.com/llms.txt` | `https://docs-platform.crewai.com/mcp` |

Old `docs.crewai.com/en/enterprise/...` links redirect to `docs-platform.crewai.com/platform/en/...` - to the matching page when it still exists (as HTML, even from a `.md` URL), otherwise to the platform introduction. Look platform topics up on `docs-platform.crewai.com` directly; its pages also serve Markdown with a `.md` suffix.

---

## When to Use This Skill

- A CrewAI feature, parameter, or behavior that the other skills do not cover
- Another skill says "re-verify with ask-docs" because the user's `crewai version` differs from the version that skill was checked against
- Current API syntax, method signatures, or configuration options
- An error message that may be covered by a troubleshooting note or caveat in the docs
- Less common features: telemetry, observability integrations, CLI commands, the tools library, AMP platform features
- Experimental conversational Flows (`handle_turn()`, `ConversationConfig`, `RouterConfig`, tracing, streaming)

**Use a sibling skill first** when it covers the topic. They hold curated guidance checked against crewai 1.15.x:

| Topic | Skill |
|---|---|
| Project scaffolding, choosing `LLM.call()` / `Agent` / `Crew` / `Flow` | getting-started |
| Agent role/goal/backstory, LLMs, memory, knowledge | design-agent |
| Task descriptions, `expected_output`, guardrails, structured output | design-task |
| Current 1.15.x API versus remembered 0.x API | check-crewai-api |
| Flow state, `@start` / `@listen` / `@router`, persistence | build-flow |
| Custom tools, `crewai_tools`, MCP servers for agents | connect-tools-and-mcp |
| Testing crews and flows with pytest, `crewai test` | test-crewai-project |
| Deploying to CrewAI AMP | deploy-to-amp |
| Calling a deployed crew over HTTP (`/kickoff`, `/status`, webhooks) | call-deployed-crew |

Use ask-docs for the gaps, and to re-check a sibling's version-sensitive rows.

---

## How to Query the Docs

Use the first path that is available.

### Path A: the docs MCP server (if configured)

The `docs.crewai.com/mcp` server needs no authentication. It exposes:

| Tool | Use |
|---|---|
| `search_crew_ai(query, version?, language?)` | Semantic search. Returns titled chunks with a `Link` per chunk |
| `query_docs_filesystem_crew_ai(command)` | Read-only shell (`rg`, `head`, `ls`, `tree`) over a virtual tree of every page and OpenAPI spec |
| `submit_feedback(path, feedback)` | Reports a docs problem to the docs team. Do not call it unless the user asks |

In Claude Code the tools appear as `mcp__<server-name>__search_crew_ai` (for example `mcp__crewai-docs__search_crew_ai`). The platform server has the same shape with a `_platform` suffix: `search_crew_ai_platform`, `query_docs_filesystem_crew_ai_platform`.

Rules learned from live use:

- **Always pass `version`** with a leading `v`, e.g. `"version": "v1.15.23"`. Without it, results mix `edge` and every hosted release (1.10.0 onward), often old ones first. `"1.15.23"` without the `v` returns "No results found".
- The filesystem is laid out as `/<version>/<lang>/<path>.mdx` (`/v1.15.23/en/concepts/knowledge.mdx`, `/edge/en/...`) plus `/openapi/<version>/enterprise-api.en.yaml`. `rg -l "restore_from_state_id" /v1.15.23/en` finds every page that mentions a symbol.
- Search results can be large (60 KB+). Prefer a focused query, then `head -120 <file>` on the page you need.
- A call occasionally fails with "Search failed". Retry once before falling back to Path B.

### Path B: llms.txt and Markdown pages (no setup)

1. Fetch the index:
   ```
   WebFetch: https://docs.crewai.com/llms.txt
   ```
   It is about 220 lines of `- [Title](https://docs.crewai.com/v1.15.23/en/<path>.md): description`, under `## Docs`, followed by `## OpenAPI Specs` (the AMP REST API YAML). The index has no category headings: find the page by title, or by path prefix (`/en/concepts/`, `/en/guides/`, `/en/learn/`, `/en/tools/`, `/en/mcp/`, `/en/observability/`, `/en/api-reference/`).
2. Fetch the page with the `.md` suffix, which returns clean Markdown (about 30 KB) instead of the rendered HTML (about 850 KB):
   ```
   WebFetch: https://docs.crewai.com/en/<path>.md
   ```
   An unversioned `/en/...` URL redirects to the latest release (`/v1.15.23/en/...` on 2026-10-01).
3. For AMP platform questions, use `https://docs-platform.crewai.com/llms.txt` the same way. It is organised by heading (Getting Started, Build, Operate, Manage, Integration Docs, Triggers, How-To Guides, API Reference).

`https://docs.crewai.com/llms-full.txt` is every page in one file (about 2 MB). Do not load it into context. Download it and search it (`curl -s ... | grep -n -A20 "restore_from_state_id"`) when the index does not point to the right page.

For conversational Flows, go straight to `https://docs.crewai.com/en/guides/flows/conversational-flows.md`. Treat it as the source of truth for the conversational API (imported from `crewai.flow`; `crewai.experimental.conversational` is a deprecated alias of the same module), which may still change.

### Path C: GitHub source of the docs

The docs live in the public `crewAIInc/crewAI` repo under `docs/<version>/<lang>/<path>.mdx`, e.g. `https://raw.githubusercontent.com/crewAIInc/crewAI/main/docs/v1.15.23/en/concepts/knowledge.mdx` or `.../docs/edge/en/...`. The older `docs/en/...` layout no longer exists (404). Use this only when the docs site is unreachable.

---

## Match the docs to the user's version

1. Run `crewai version` (or `uv run python -c "import crewai; print(crewai.__version__)"` in a uv project).
2. Read the docs for that release: the URL prefix `https://docs.crewai.com/v<X.Y.Z>/en/<path>.md`, or `version: "v<X.Y.Z>"` on the MCP server. Releases from 1.10.0 onward are hosted, plus `edge` (unreleased main). Only the root `llms.txt` exists - `/v<X.Y.Z>/llms.txt` is a 404 - so take the path from the root index and swap the version prefix.
3. If the user's release is not hosted, read the nearest hosted one and say so. A non-hosted version does not 404: `/v1.9.0/en/concepts/knowledge.md` redirects to the home page with status 200, so check that the page you got is the page you asked for.

---

## Docs can be wrong: check against the installed package

The docs are the best index of what exists, not proof that a snippet runs. Example found on 2026-10-01: the "Forking Persisted State" example in the v1.15.23 Mastering Flow State guide decorates the class with bare `@persist`. On crewai 1.15.23 that raises `TypeError: persist.<locals>.decorator() missing 1 required positional argument: 'target'` when the flow is created. `@persist()` works.

Before giving the user code that matters:

- Check signatures against the installed package: `python -c "import inspect, crewai.flow.flow as m; print(inspect.signature(m.Flow.kickoff))"`.
- Run the smallest snippet that exercises the claim, if it needs no API key.
- If the docs and the package disagree, say so, give the version that works, and cite both. The check-crewai-api skill lists known differences between remembered and current APIs.

---

## Workflow Summary

1. **Understand the question** - which concept, API, or behavior, and which crewai version?
2. **Pick the site** - framework (`docs.crewai.com`) or AMP platform (`docs-platform.crewai.com`).
3. **Query** - MCP with `version` set, or `llms.txt` then the `.md` page for that version.
4. **Check it** - signatures or a small run against the installed package when code is involved.
5. **Answer and cite** - give the docs URL (with the version prefix) so the user can read further.

---

## Worked examples (checked 2026-10-01 against crewai 1.15.23)

| Question | Where the answer is | What the docs say, checked |
|---|---|---|
| "How do I persist a flow?" | `/en/guides/flows/mastering-flow-state.md`, `/en/guides/flows/inputs-id-deprecation.md` | Decorate the Flow class (or a method) with `@persist()` from `crewai.flow.persistence`; state needs an `id`. `kickoff(restore_from_state_id=...)` forks from a saved state under a new `state.id`; `kickoff(inputs={"id": ...})` resumes under the same id and is documented as deprecated (1.15.23 emits no warning). Both ran locally |
| "What does POST /kickoff take?" | `/en/api-reference/kickoff.md` | JSON body with required `inputs` (string values) and optional `meta`, `taskWebhookUrl`, `stepWebhookUrl`, `crewWebhookUrl`; returns `{"kickoff_id": ...}`; bearer token auth. The installed `crewai_tools` `InvokeCrewAIAutomationTool` posts the same `{"inputs": ...}` body. call-deployed-crew covers the full client |
| "How do I set an embedder for knowledge?" | `/en/concepts/knowledge.md` | Pass `embedder={"provider": ..., "config": {...}}` on the `Crew` (or on an `Agent`). The default is OpenAI embeddings even with a non-OpenAI LLM; without `OPENAI_API_KEY` the knowledge upsert logs an error. A crew with an Anthropic LLM and `{"provider": "onnx", "config": {}}` answered from its knowledge source |

Other good uses:

| User question | Why this skill |
|---|---|
| "What parameters does `Crew()` accept?" | API reference - check it against the installed signature |
| "How do I turn off telemetry?" | `/en/telemetry.md` for what is collected; the test-crewai-project skill has the exact switch values, checked against the installed package |
| "What CLI commands does `crewai` support?" | `/en/concepts/cli.md`, then `crewai --help` on the installed version |
| "What tools are available for web scraping?" | Tools library pages under `/en/tools/` |
| "How do I set up RBAC on AMP?" | `docs-platform.crewai.com` (`/platform/en/features/rbac`) |
| "How do I build a chat app with `Flow.handle_turn()`?" | Experimental conversational Flow API; read the latest guide |

---

## Setting Up the Docs MCP Server (optional)

Path B works with no setup. For structured search, add the server to the coding agent. Each of these was run on 2026-10-01 against a throwaway config directory.

**Claude Code** (`claude mcp add`):

```bash
claude mcp add --transport http crewai-docs https://docs.crewai.com/mcp
# --scope project writes .mcp.json in the repo instead; --scope user makes it global
claude mcp list   # shows "crewai-docs: https://docs.crewai.com/mcp (HTTP) - Connected"
```

The project-scope `.mcp.json` it writes:

```json
{
  "mcpServers": {
    "crewai-docs": {
      "type": "http",
      "url": "https://docs.crewai.com/mcp"
    }
  }
}
```

**Codex CLI** - `codex mcp add crewai-docs --url https://docs.crewai.com/mcp`, which writes this to `~/.codex/config.toml` (or `$CODEX_HOME/config.toml`):

```toml
[mcp_servers.crewai-docs]
url = "https://docs.crewai.com/mcp"
```

**Cursor** - add to `.cursor/mcp.json` in the project, or `~/.cursor/mcp.json` for all projects ([Cursor MCP docs](https://cursor.com/docs/mcp)):

```json
{
  "mcpServers": {
    "crewai-docs": { "url": "https://docs.crewai.com/mcp" }
  }
}
```

Other agents: add `https://docs.crewai.com/mcp` as a remote (streamable HTTP) MCP server. Add `https://docs-platform.crewai.com/mcp` the same way for AMP platform docs.

---

## Related Skills

- **getting-started** - project scaffolding, choosing abstractions, Flow architecture
- **design-agent** - agent Role-Goal-Backstory, parameter tuning, tools, memory and knowledge
- **design-task** - task descriptions, expected_output, guardrails, structured output, dependencies
- **check-crewai-api** - current 1.15.x API versus the 0.x API assistants remember
- **build-flow** - Flow state, decorators, routing, persistence
- **connect-tools-and-mcp** - custom tools, `crewai_tools`, MCP servers for agents
- **test-crewai-project** - deterministic pytest testing of crews and flows
- **deploy-to-amp** - getting a crew or flow onto CrewAI AMP
- **call-deployed-crew** - calling a deployed crew over HTTP
