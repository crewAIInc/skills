# MCP Servers Reference

How to use official MCP (Model Context Protocol) servers in CrewAI — prefer these over native `crewai_tools` when an official server exists.

Verified against crewai 1.15.23 on 2026-10-01 (string refs, `#tool` filters and `MCPServerHTTP` discovery were run against the public Exa MCP server; `MCPServerStdio` with `tool_filter` against `uvx mcp-server-time`). The **connect-tools-and-mcp** skill covers the same API in more depth.

---

## Why Prefer Official MCP Servers

Official MCP servers are **maintained by the service providers themselves** (GitHub, Stripe, Snowflake, etc.). This means:

- **Always up to date** — API changes are reflected by the provider, not the crewAI community
- **Richer tool coverage** — providers expose their full API surface, not just the subset crewAI wrapped
- **Standardized protocol** — MCP is an open standard; tools are auto-discovered and integrated
- **Less dependency bloat** — no need for per-service Python packages in your project

**Decision rule:** If an official MCP server exists for the service you need, use it. Fall back to native `crewai_tools` only when no official MCP server is available.

---

## Installation

```bash
# Simple DSL integration (mcps=[...]): nothing to install - `mcp` is already a core crewai dependency

# Advanced MCPServerAdapter usage only
uv add "crewai-tools[mcp]"
```

---

## Attaching MCP Servers to Agents

### Simple DSL — `mcps` Field (Recommended)

The `mcps` field on an Agent accepts string references or structured configs. This is the preferred approach.

```python
from crewai import Agent

agent = Agent(
    role="Research Analyst",
    goal="Research and analyze information",
    backstory="Expert researcher with access to multiple data sources.",
    mcps=[
        "https://mcp.exa.ai/mcp",                       # Remote HTTP server (must start with https://)
        "https://mcp.example.com/mcp#get_forecast",     # Specific tool via #
        "snowflake",                                    # Integration connected in your CrewAI AMP account
        "stripe#list_invoices",                         # Specific tool from an AMP-connected integration
        "github#search_repositories",                   # GitHub, via AMP
    ]
)
```

Bare slugs (`"snowflake"`, `"stripe#..."`, `"github"`) are **CrewAI AMP integration references**: the server config is fetched from your AMP account, so the integration must be connected there and the run must be able to authenticate to AMP. A string that is neither an `https://` URL nor a valid slug - `"http://localhost:8000/mcp"`, or a slug with a comma list such as `"github#a,b"` - is rejected when the Agent is built: `ValidationError ... Invalid MCP reference: '...'. String references must be an 'https://' URL or a valid slug`. Use `MCPServerHTTP` for `http://` URLs.

`https://` strings resolve their tools with `asyncio.run()`, so inside a running event loop - `await crew.akickoff()`, or a crew deployed on CrewAI AMP - they yield **zero tools with no error**. For async code and deployed crews use `MCPServerHTTP(url="https://...")` instead (verified in the **connect-tools-and-mcp** skill).

### String Reference Formats

| Format | Example | What It Does |
|---|---|---|
| HTTPS URL | `"https://mcp.exa.ai/mcp"` | Connect to remote MCP server (sync `kickoff()` only - see above) |
| URL + tool filter | `"https://mcp.example.com/mcp#get_forecast"` | Connect but only expose `get_forecast` |
| AMP slug | `"snowflake"` | Use an integration connected in your CrewAI AMP account (all tools) |
| AMP slug + filter | `"stripe#list_invoices"` | Same, expose only `list_invoices` |

`#` takes exactly **one** tool name. Keep credentials out of URL strings - use `MCPServerHTTP(headers=...)` below.

### Structured Configurations (Full Control)

Use these when you need custom env vars, headers, or tool filtering.

**Stdio — Local MCP Servers**

The server process does not inherit your environment: it gets only `HOME, LOGNAME, PATH, SHELL, TERM, USER` plus `env=`, so pass its API keys in `env` explicitly.

```python
from crewai.mcp import MCPServerStdio

filesystem_server = MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
    cache_tools_list=True,
)

agent = Agent(
    role="File Manager",
    goal="Read and manage project files",
    backstory="...",
    mcps=[filesystem_server],
)
```

**HTTP — Remote MCP Servers**

```python
from crewai.mcp import MCPServerHTTP

http_server = MCPServerHTTP(
    url="https://api.example.com/mcp",
    headers={"Authorization": "Bearer your_token"},
    streamable=True,
    cache_tools_list=True,
)

agent = Agent(
    role="Data Analyst",
    goal="Query external data sources",
    backstory="...",
    mcps=[http_server],
)
```

**SSE — Real-Time Streaming**

```python
from crewai.mcp import MCPServerSSE

sse_server = MCPServerSSE(
    url="https://stream.example.com/mcp/sse",
    headers={"Authorization": "Bearer your_token"},
    cache_tools_list=True,
)

agent = Agent(
    role="Monitor",
    goal="Track real-time events",
    backstory="...",
    mcps=[sse_server],
)
```

---

## Tool Filtering

Limit which tools an agent can access from an MCP server:

```python
from crewai.mcp import MCPServerStdio, create_static_tool_filter

server = MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "./data"],   # needs an allowed dir: crewai does not send MCP roots
    tool_filter=create_static_tool_filter(
        allowed_tool_names=["read_text_file", "list_directory"]
    ),
)
```

Or use the `#tool_name` shorthand in string references - one reference per tool:

```python
mcps=["github#search_repositories", "github#list_issues"]
```

A comma list never works: on a slug (`"github#search_repositories,list_issues"`) it raises the `Invalid MCP reference` ValidationError above; on an `https://` URL it is accepted but selects **zero** tools, with no error (verified: `"https://mcp.exa.ai/mcp#web_search_exa,web_fetch_exa"` -> `[]`, while `#web_search_exa` alone -> one tool). `tool_filter` names are matched against the sanitized tool name (a server tool `getForecast` is listed as `get_forecast`).

---

## Mixing MCP Servers with Native Tools

You can combine `mcps`, native `tools`, and platform `apps` on the same agent:

```python
from crewai import Agent
from crewai_tools import SerperDevTool  # Native tool (no official MCP server for Serper)

agent = Agent(
    role="Full-Featured Researcher",
    goal="Research using all available sources",
    backstory="...",
    tools=[SerperDevTool()],            # Native tool — no MCP alternative
    mcps=[                               # Official MCP servers
        "https://mcp.exa.ai/mcp",
        "github",                         # AMP-connected integration
    ],
)
```

---

## Known Official MCP Servers

These are servers maintained by the service providers or the MCP ecosystem. **Use these instead of native `crewai_tools` equivalents when available.**

| Service | MCP Reference | Replaces Native Tool |
|---|---|---|
| GitHub | `"github"` (AMP), or GitHub's own server (github/github-mcp-server); the npm `@modelcontextprotocol/server-github` is deprecated but still runs and reads `GITHUB_PERSONAL_ACCESS_TOKEN` | `GithubSearchTool` |
| Filesystem | `MCPServerStdio` with `@modelcontextprotocol/server-filesystem` | `FileReadTool`, `DirectoryReadTool` |
| Exa (search) | `"https://mcp.exa.ai/mcp"`, or `MCPServerHTTP` with your key in `headers={"x-api-key": ...}` | `EXASearchTool` |
| Stripe | `"stripe"` (AMP) | - |
| Snowflake | `"snowflake"` (AMP) | `SnowflakeSearchTool` |
| Slack | `"slack"` (AMP) | - |

`(AMP)` = an integration slug that needs a CrewAI AMP account with that integration connected.

> **Note:** The MCP ecosystem is growing rapidly. Check [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) for the latest official servers. If a provider publishes an MCP server, prefer it over the `crewai_tools` wrapper.

---

## Automatic Behaviors

- **Tool prefixing** - tools are offered to the LLM as `<server>_<tool>`, sanitized: `"https://mcp.exa.ai/mcp"` gives `mcp_exa_ai_mcp_web_search_exa`; `MCPServerStdio(command="uvx", args=["mcp-server-time"])` gives `uvx_mcp_server_time_get_current_time` (the tool object's `.name` keeps the raw `uvx_mcp-server-time_get_current_time`). Do not hard-code these names in prompts
- **On-demand connections** - nothing connects at agent construction; tools are discovered when a task runs
- **Schema caching** - tool schemas are cached for 5 minutes (`https://` strings always; config objects when `cache_tools_list=True`)
- **Failures** - an unreachable `https://` string yields no tools and the run continues (so does a reachable one inside a running event loop, above); an unreachable `MCPServerStdio/HTTP/SSE` config raises `MCPConnectionError` at kickoff

## Timeouts

None of these can be changed through a config or Agent field in 1.15.23:

| Path | Connection | Tool discovery | Tool execution |
|---|---|---|---|
| `"https://..."` string | 10 s | 15 s | 60 s |
| `MCPServerStdio/HTTP/SSE` configs and AMP slugs | 30 s | 30 s | 30 s (retried up to 3 times - keep tools fast and idempotent) |

---

## Advanced: MCPServerAdapter (Manual Lifecycle)

For scenarios where you need explicit control over connection start/stop:

```python
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

# @modelcontextprotocol/server-github is deprecated on npm (it still runs); shown for the adapter pattern.
server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-github"],
    env={"GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>"},   # the variable this server reads
)

# Context manager (recommended) — auto-starts and stops
with MCPServerAdapter(server_params) as tools:
    agent = Agent(
        role="GitHub Analyst",
        goal="Analyze repository activity",
        backstory="...",
        tools=tools,
    )
    result = agent.kickoff("List recent issues in crewAIInc/crewAI")

# Manual lifecycle (when you need more control)
adapter = MCPServerAdapter(server_params)   # the constructor starts the server; calling start() again raises
try:
    tools = adapter.tools
    # ... use tools with agents ...
finally:
    adapter.stop()  # MUST call stop() to terminate the server process
```

---

## Decision Checklist

When adding a tool capability to an agent:

1. **Does an official MCP server exist?** → Use `mcps=["service"]` or structured config
2. **Is there a well-maintained community MCP server?** → Use `MCPServerStdio` with the npm/pip package
3. **Neither?** → Use the native `crewai_tools` equivalent
4. **No crewai_tools equivalent either?** → Build a custom tool with `@tool` or `BaseTool`
