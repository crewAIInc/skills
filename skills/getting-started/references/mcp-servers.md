# MCP Servers Reference

How to use official MCP (Model Context Protocol) servers in CrewAI — prefer these over native `crewai_tools` when an official server exists.

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
# For simple DSL integration (recommended)
uv add mcp

# For advanced MCPServerAdapter usage
uv pip install 'crewai-tools[mcp]'
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
        "https://mcp.exa.ai/mcp?api_key=your_key",   # Remote HTTP server
        "https://weather.api.com/mcp#get_forecast",    # Specific tool via #
        "snowflake",                                    # Connected MCP (catalog)
        "stripe#list_invoices",                         # Specific tool from catalog
        "github#search_repositories",                   # GitHub official MCP
    ]
)
```

### String Reference Formats

| Format | Example | What It Does |
|---|---|---|
| HTTPS URL | `"https://mcp.exa.ai/mcp?api_key=KEY"` | Connect to remote MCP server |
| URL + tool filter | `"https://weather.api.com/mcp#get_forecast"` | Connect but only expose `get_forecast` |
| Catalog slug | `"snowflake"` | Use a connected MCP from the catalog (all tools) |
| Catalog slug + filter | `"stripe#list_invoices"` | Use a connected MCP, expose only `list_invoices` |

### Structured Configurations (Full Control)

Use these when you need custom env vars, headers, or tool filtering.

**Stdio — Local MCP Servers**

```python
from crewai.mcp import MCPServerStdio

filesystem_server = MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
    env={"UV_PYTHON": "3.12"},
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
    args=["-y", "@modelcontextprotocol/server-filesystem"],
    tool_filter=create_static_tool_filter(
        allowed_tool_names=["read_file", "list_directory"]
    ),
)
```

Or use the `#tool_name` shorthand in string references:

```python
mcps=["github#search_repositories,list_issues"]
```

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
        "https://mcp.exa.ai/mcp?api_key=key",
        "github",
    ],
)
```

---

## Known Official MCP Servers

These are servers maintained by the service providers or the MCP ecosystem. **Use these instead of native `crewai_tools` equivalents when available.**

| Service | MCP Reference | Replaces Native Tool |
|---|---|---|
| GitHub | `"github"` or `MCPServerStdio` with `@modelcontextprotocol/server-github` | `GithubSearchTool` |
| Filesystem | `MCPServerStdio` with `@modelcontextprotocol/server-filesystem` | `FileReadTool`, `DirectoryReadTool` |
| Exa (search) | `"https://mcp.exa.ai/mcp?api_key=KEY"` | `EXASearchTool` |
| Stripe | `"stripe"` | — |
| Snowflake | `"snowflake"` | `SnowflakeSearchTool` |
| Slack | `"slack"` | — |

> **Note:** The MCP ecosystem is growing rapidly. Check [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) for the latest official servers. If a provider publishes an MCP server, prefer it over the `crewai_tools` wrapper.

---

## Automatic Behaviors

- **Tool prefixing** — tools are auto-prefixed to avoid name collisions (e.g., `mcp_exa_ai_search`)
- **On-demand connections** — MCP connections are established during tool execution, not at agent init
- **Schema caching** — tool schemas are cached for 5 minutes across agent instances
- **Graceful failures** — if an MCP server is unreachable, the agent continues with remaining tools

## Timeouts

| Timeout | Default |
|---|---|
| Connection | 10 seconds |
| Tool discovery | 15 seconds |
| Tool execution | 30 seconds |

---

## Advanced: MCPServerAdapter (Manual Lifecycle)

For scenarios where you need explicit control over connection start/stop:

```python
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters

server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-github"],
    env={"GITHUB_TOKEN": "your_token"},
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
adapter = MCPServerAdapter(server_params=server_params)
try:
    adapter.start()
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
