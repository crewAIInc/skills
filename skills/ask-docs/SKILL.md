---
name: ask-docs
description: "Query the official CrewAI documentation for answers. Use when the user has a CrewAI question that isn't fully covered by the getting-started, design-agent, design-task skills — e.g., specific API details, configuration options, advanced features, troubleshooting errors, enterprise features, tool references, or anything where the latest docs are the best source of truth."
---

# Ask CrewAI Docs

Answer CrewAI questions by looking up the official documentation at `docs.crewai.com`.

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

### Step 1: Fetch the docs index

The CrewAI docs site publishes an `llms.txt` file — a structured index of every documentation page with descriptions. Fetch it first to find the right page:

```
WebFetch: https://docs.crewai.com/llms.txt
```

This returns a categorized list of all doc pages in the format:

```
- [Page Title](https://docs.crewai.com/path/to/page): "Description of what the page covers"
```

Categories include:
- **API Reference** — REST endpoints (kickoff, status, resume, inputs)
- **Concepts** — agents, crews, tasks, tools, flows, memory, knowledge, LLMs, processes, training, testing
- **Enterprise** — RBAC, SSO, automations, traces, deployment, triggers, integrations
- **Tools Library** — 40+ tools organized by category (AI/ML, automation, cloud, database, files, search, web scraping)
- **MCP Integration** — MCP server setup, transports, DSL, security
- **Examples & Cookbooks** — practical implementations
- **Learning Paths** — tutorials and advanced topics
- **Observability** — monitoring integrations

### Step 2: Fetch the relevant page

Once you identify the right page from the index, fetch its content:

```
WebFetch: https://docs.crewai.com/<path-from-index>
```

### Step 3: Synthesize and cite

Combine what you find from the docs with context from the other skills to give a clear, actionable response. Always include the docs URL so the user can read further.

---

## Workflow Summary

1. **Understand the user's question** — what specific CrewAI concept, API, or behavior are they asking about?
2. **Fetch `llms.txt`** — scan the index to find the most relevant page(s)
3. **Fetch the page(s)** — retrieve the actual documentation content
4. **Synthesize the answer** — combine docs content with context from other skills
5. **Cite the source** — include the docs URL in your response

---

## For an Even Better Experience

Users who frequently query CrewAI docs can configure the CrewAI docs MCP server in their coding agent for richer, structured search:

```
https://docs.crewai.com/mcp
```

This is optional — the `llms.txt` workflow above works without any setup.

---

## Examples of Good Use Cases

| User Question | Why This Skill |
|---|---|
| "What parameters does `Crew()` accept?" | Specific API reference — docs are authoritative |
| "How do I set up telemetry in CrewAI?" | Niche feature not covered in other skills |
| "What's the difference between `Process.sequential` and `Process.hierarchical`?" | Detailed comparison best sourced from docs |
| "I'm getting `ValidationError` when using `output_pydantic`" | Troubleshooting — docs may have known issues or caveats |
| "How do I deploy a CrewAI flow to production?" | Deployment guidance lives in docs, not in design skills |
| "What CLI commands does `crewai` support?" | CLI reference is a docs concern |
| "How do I configure memory for a crew?" | Detailed config options beyond what design-agent covers |
| "What tools are available for web scraping?" | Tools library reference |
| "How do I set up SSO for CrewAI enterprise?" | Enterprise features live in docs |

---

## Related Skills

- **getting-started** — project scaffolding, choosing abstractions, Flow architecture
- **design-agent** — agent Role-Goal-Backstory, parameter tuning, tools, memory & knowledge
- **design-task** — task descriptions, expected_output, guardrails, structured output, dependencies
