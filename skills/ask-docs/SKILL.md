---
name: ask-docs
description: "Looks up answers in the official CrewAI docs at docs.crewai.com. Use when the user asks a CrewAI question that needs authoritative current docs — specific API details, method signatures, CLI commands, enterprise features, the built-in tools/MCP catalog, deployment, telemetry, or an unfamiliar error message. Fills gaps left by getting-started, design-agent, and design-task, and verifies knowledge against the latest published docs."
---

# Ask CrewAI Docs

Answer CrewAI questions by querying the official documentation at `docs.crewai.com`.

---

## When to Use This Skill

Use this skill when:

- The user asks about a CrewAI feature, parameter, or behavior not covered in detail by the other skills
- You need to verify current API syntax, method signatures, or configuration options
- The user hits an error and needs troubleshooting guidance from official docs
- The question is about a newer or less common CrewAI feature (e.g., telemetry, testing, CLI commands, deployment, enterprise features)
- You're unsure whether your knowledge is current — the docs reflect the latest published state

**Do NOT use this skill** when the question is clearly answered by one of the other skills (getting-started, design-agent, design-task). Those skills contain curated, opinionated guidance. This skill is for filling gaps and verifying details.

---

## How to Query the Docs

CrewAI publishes a live MCP server for its docs at `https://docs.crewai.com/mcp`. **Prefer the MCP path** when it's available — it returns structured, search-ranked results without burning context on full-page fetches. Fall back to direct `WebFetch` only when the MCP server isn't registered.

### Path A — MCP server (preferred)

The CrewAI docs MCP server exposes two tools. In Claude Code they appear under whatever name the user gave the server (commonly `crewai-docs`), so the fully-qualified names look like `mcp__crewai-docs__search_crew_ai`. Adjust the prefix to match the user's MCP config.

**Tool 1: `search_crew_ai`** — broad semantic search across the knowledge base.

| Parameter | Required | Purpose |
|---|---|---|
| `query` | yes | Natural-language question |
| `version` | no | Pin to a docs version |
| `language` | no | Pin to a language |

Use for conceptual questions: *"how does CrewAI memory work?"*, *"what guardrails are available for tasks?"*, *"difference between sequential and hierarchical processes?"*

**Tool 2: `query_docs_filesystem_crew_ai`** — read-only filesystem queries against the docs sandbox.

| Parameter | Required | Purpose |
|---|---|---|
| `command` | yes | A shell-style command — supports `ripgrep`, `grep`, `find`, `tree`, `ls`, `cat`, `head`, `tail`, and text utilities |

Use for exact-match work: locating every page that mentions a specific symbol, reading a full page by path, or enumerating sections of the docs tree.

**When to use which:**
- Reach for `search_crew_ai` first for almost everything — it's the right default.
- Switch to `query_docs_filesystem_crew_ai` when you need an exact identifier (`max_iter`, `output_pydantic`), a specific file path, or a structural view of the docs.

#### Checking if the MCP server is registered

Look for tool names matching `mcp__*__search_crew_ai` in the available tool list. If none appear, the user hasn't registered the server — fall through to Path B and optionally suggest they add it (see the bottom of this file).

### Path B — WebFetch fallback

If the MCP server isn't available, use the published `llms.txt` index plus targeted page fetches.

**Step 1: Fetch the docs index**

```
WebFetch: https://docs.crewai.com/llms.txt
```

This returns a categorized list of every doc page:

```
- [Page Title](https://docs.crewai.com/path/to/page): "Description of what the page covers"
```

Categories include API Reference, Concepts, Enterprise, Tools Library, MCP Integration, Examples & Cookbooks, Learning Paths, and Observability.

**Step 2: Fetch the relevant page**

```
WebFetch: https://docs.crewai.com/<path-from-index>
```

**Step 3: Synthesize and cite**

Combine the docs content with context from the other skills. Always include the docs URL so the user can read further.

---

## Workflow Summary

1. **Understand the question** — what specific CrewAI concept, API, or behavior is the user asking about?
2. **Pick a path** — MCP if `mcp__*__search_crew_ai` is available, otherwise WebFetch.
3. **Query** — `search_crew_ai` for conceptual, `query_docs_filesystem_crew_ai` for exact / structural, `llms.txt` + page fetch on the fallback path.
4. **Synthesize** — combine the result with context from the other skills.
5. **Cite** — include the docs URL in your response so the user can read further.

---

## Examples of Good Use Cases

| User Question | Best Tool | Why |
|---|---|---|
| "What parameters does `Crew()` accept?" | `query_docs_filesystem_crew_ai` (grep for `Crew(`) | Exact symbol lookup |
| "How does CrewAI memory work?" | `search_crew_ai` | Conceptual / broad |
| "What's the difference between `Process.sequential` and `Process.hierarchical`?" | `search_crew_ai` | Comparison question |
| "I'm getting `ValidationError` when using `output_pydantic`" | `query_docs_filesystem_crew_ai` (grep error string) | Error-message lookup |
| "How do I deploy a CrewAI flow to production?" | `search_crew_ai` | Workflow / deployment guide |
| "What CLI commands does `crewai` support?" | `search_crew_ai` | CLI reference page |
| "How do I configure memory for a crew?" | `search_crew_ai` | Detailed config beyond design-agent |
| "What tools are available for web scraping?" | `search_crew_ai` | Tools library catalog |
| "How do I set up SSO for CrewAI enterprise?" | `search_crew_ai` | Enterprise docs |

---

## Suggesting the MCP server to users

If you fall back to Path B repeatedly for the same user, mention once that they can register the CrewAI docs MCP server for faster, richer search:

```
https://docs.crewai.com/mcp
```

Don't push this — Path B works fine without it.

---

## Related Skills

- **getting-started** — project scaffolding, choosing abstractions, Flow architecture
- **design-agent** — agent Role-Goal-Backstory, parameter tuning, tools, memory & knowledge
- **design-task** — task descriptions, expected_output, guardrails, structured output, dependencies
