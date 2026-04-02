---
name: ask-docs
description: "Query the official CrewAI documentation via its live MCP server. Use when the user has a CrewAI question that isn't fully covered by the getting-started, design-agent, design-task, or optimize-flow skills — e.g., specific API details, configuration options, advanced features, troubleshooting errors, or anything where the latest docs are the best source of truth."
---

# Ask CrewAI Docs

Use the live CrewAI documentation to answer questions with up-to-date, authoritative information.

---

## When to Use This Skill

Use this skill when:

- The user asks about a CrewAI feature, parameter, or behavior not covered in detail by the other skills
- You need to verify current API syntax, method signatures, or configuration options
- The user hits an error and needs troubleshooting guidance from official docs
- The question is about a newer or less common CrewAI feature (e.g., telemetry, testing, CLI commands, deployment, enterprise features)
- You're unsure whether your knowledge is current — the docs reflect the latest published state

**Do NOT use this skill** when the question is clearly answered by one of the other skills (getting-started, design-agent, design-task, optimize-flow). Those skills contain curated, opinionated guidance. This skill is for filling gaps and verifying details.

---

## How to Query the Docs

Try the approaches below in order. Use the first one that's available.

### Option 1: CrewAI Docs MCP Server (Preferred)

If the `crewai-docs` MCP server is configured, use its tools directly to search and read documentation. This is the best experience — structured search with full page content.

<!--### Option 2: WebFetch Fallback

If the MCP server is not configured, fall back to fetching docs via the web:

1. **Find the right page** — fetch the docs index to locate the relevant page:
   ```
   WebFetch: https://docs.crewai.com/llms.txt
   ```
   This returns a sitemap of all doc pages with descriptions. Identify the URL most relevant to the user's question.

2. **Fetch the page** — retrieve the specific doc page content:
   ```
   WebFetch: https://docs.crewai.com/<path-from-index>
   ```

3. **Synthesize the answer** — combine what you find with context from the other skills to give a clear, actionable response.

4. **Cite the source** — include the docs URL so the user can read further.

After using the fallback, suggest the user configure the MCP server for a better experience:

> **Tip:** For faster docs lookups, add the CrewAI docs MCP server to your coding agent:
> `https://docs.crewai.com/mcp`-->

---

## Setting Up the MCP Server (Recommended)

For the best experience, configure the CrewAI documentation MCP server in your coding agent.

**Server URL:**
```
https://docs.crewai.com/mcp
```

### Claude Code

Add to `.claude/settings.json` (project-level) or `~/.claude/settings.json` (global):

```json
{
  "mcpServers": {
    "crewai-docs": {
      "type": "url",
      "url": "https://docs.crewai.com/mcp"
    }
  }
}
```

### Cursor / Windsurf / Other Agents

Add `https://docs.crewai.com/mcp` as a remote MCP server following your tool's MCP configuration docs.

---

## Workflow

1. **Understand the user's question** — what specific CrewAI concept, API, or behavior are they asking about?
2. **Query the docs** — use the MCP tools if available, otherwise WebFetch the relevant page
3. **Synthesize the answer** — combine what you find from the docs with context from the other skills to give a clear, actionable response
4. **Cite the source** — mention which docs page the information came from so the user can read further

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

---

## Related Skills

- **getting-started** — project scaffolding, choosing abstractions, Flow architecture
- **design-agent** — agent Role-Goal-Backstory, parameter tuning, tools, memory & knowledge
- **design-task** — task descriptions, expected_output, guardrails, structured output, dependencies
- **optimize-flow** — Flow latency optimization, parallelization, model tiering
