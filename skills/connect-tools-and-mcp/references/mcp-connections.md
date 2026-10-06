# MCP Connections Reference

Every way to attach an MCP server to a crewAI agent on crewai 1.15.22-1.15.23, how tool names come out, timeouts, and what survives a hosted deployment.

---

## 1. Native configs (`crewai.mcp`)

```python
import os
from crewai import Agent
from crewai.mcp import MCPServerStdio, MCPServerHTTP, MCPServerSSE

local = MCPServerStdio(
    command="uvx",                         # keep command/args short: they become part of tool names
    args=["mcp-server-time"],
    env={"TZ": "UTC"},                     # the server gets ONLY these plus HOME, LOGNAME, PATH, SHELL, TERM, USER
    cache_tools_list=True,
)
remote = MCPServerHTTP(
    url="https://mcp.example.com/mcp",
    headers={"Authorization": f"Bearer {os.environ.get('ACME_MCP_TOKEN', '<your-key>')}"},
    streamable=True,                       # default; streamable HTTP transport
)
legacy = MCPServerSSE(url="https://legacy.example.com/sse")

agent = Agent(role="Ops assistant", goal="Answer ops questions", backstory="Precise.",
              mcps=[local, remote, legacy])
```

| Config | Fields (complete list) |
|---|---|
| `MCPServerStdio` | `command`, `args`, `env`, `tool_filter`, `cache_tools_list` |
| `MCPServerHTTP` | `url`, `headers`, `streamable`, `tool_filter`, `cache_tools_list` |
| `MCPServerSSE` | `url`, `headers`, `tool_filter`, `cache_tools_list` |

There is no `cwd`, `timeout` or `name` field. Relative paths in `args` resolve against the working directory of the crew process; `args=["-m", "<pkg>.server"]` avoids depending on it.

Give `MCPServerHTTP`/`MCPServerSSE` a hostname, not an IP address. The URL becomes the tool-name prefix, and a name that starts with a digit is rejected by Anthropic models: `ValueError: Anthropic function name '127_0_0_1_8765_mcp_lookup_stock' must start with a letter or underscore` (live run). `http://localhost:8765/mcp` gives `localhost_8765_mcp_lookup_stock` and works.

A stdio server does not inherit the crew's environment. It starts with the MCP SDK's default set (`HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM`, `USER`; on Windows `APPDATA`, `PATH`, `USERPROFILE`, ...) plus whatever you put in `env=`. Verified: with `ACME_TOKEN` set in the crew process, the server reported `ACME_TOKEN visible: False` until it was passed via `env={"ACME_TOKEN": os.environ["ACME_TOKEN"]}`.

Connections are made when a task executes, not when the Agent is built. Every tool call opens a fresh client to the server, so concurrent calls do not share a session.

---

## 2. String references

```python
from crewai import Agent

agent = Agent(
    role="Researcher", goal="Find facts", backstory="Thorough.",
    mcps=[
        "https://docs.example.com/mcp",               # every tool on the server
        "https://search.example.com/mcp#web_search",  # only web_search
        "acme",                                       # AMP-connected integration, all tools
        "acme#lookup_stock",                          # one tool per ref
        "acme#list_warehouses",
    ],
)
```

| String | How it is resolved (verified) |
|---|---|
| starts with `https://` | Connected directly over streamable HTTP. `#name` keeps the tool whose sanitized name equals `name`. Discovery uses `asyncio.run()`, so inside a running event loop (`await crew.akickoff()`, a crew deployed on CrewAI AMP) the ref yields **zero tools with no error** - verified live both ways. Use `MCPServerHTTP` there |
| anything else | Treated as a CrewAI AMP integration slug. The legacy `crewai-amp:` prefix is stripped. The config is fetched from your AMP account, so the integration must be connected there and the run must be able to authenticate to AMP |
| `"http://localhost:8000/mcp"`, `"localhost:8000"` | Rejected when the Agent is built: `ValidationError ... Invalid MCP reference: 'http://localhost:8000/mcp'. String references must be an 'https://' URL or a valid slug (e.g. 'notion', 'notion#search', 'crewai-amp:notion')`. Use `MCPServerHTTP(url="http://...")` |
| `"slug#a,b"` | Rejected with the same ValidationError (a slug's `#` part allows one name of letters, digits, `_`, `-`) |
| `"https://...#a,b"` | Accepted, but zero tools: `a,b` sanitizes to `a_b`, which matches nothing (verified live against a public server) |
| slug not connected | Zero tools from that slug and an `MCPConfigFetchFailedEvent`; the run continues (also seen on an AMP deployment: run SUCCESS, agent had no tools) |

---

## 3. Filtering tools

```python
from crewai.mcp import MCPServerStdio, create_static_tool_filter, create_dynamic_tool_filter

only_reads = MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "./data"],
    tool_filter=create_static_tool_filter(
        allowed_tool_names=["read_text_file", "list_directory"],   # read_file is deprecated in this server
        blocked_tool_names=["write_file"],          # blocked wins over allowed
    ),
)

def no_destructive(context, tool):
    """context: ToolFilterContext(agent, server_name, run_context); tool: dict with 'name', 'description', ..."""
    return not tool["name"].startswith(("write", "edit", "move"))

guarded = MCPServerStdio(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "./data"],
                         tool_filter=create_dynamic_tool_filter(no_destructive))
```

Filters see the **sanitized** tool name. A server tool called `getForecast` must appear in the filter as `get_forecast`. `allowed_tool_names=["getForecast"]` keeps nothing (verified).

---

## 4. How tool names are built

| Form | Raw name | Offered to the LLM as |
|---|---|---|
| `MCPServerStdio(command="uvx", args=["mcp-server-time"])`, tool `get_current_time` | `uvx_mcp-server-time_get_current_time` | `uvx_mcp_server_time_get_current_time` |
| `MCPServerStdio(command="python", args=["servers/inventory.py"])`, tool `lookup_stock` | `python_servers/inventory.py_lookup_stock` | `python_servers_inventory_py_lookup_stock` |
| `MCPServerStdio` with absolute interpreter and script paths | longer than 64 chars | first 55 chars + `_` + 8-char hash, e.g. `opt_app_venv_bin_python_opt_app_servers_inventory_serve_a87662e9` - the tool name is no longer visible |
| `MCPServerHTTP` / `MCPServerSSE` / `https://` string at `https://api.example.com:8443/v1/mcp`, tool `getForecast` | `api_example_com:8443_v1_mcp_get_forecast` | `api_example_com_8443_v1_mcp_get_forecast` |
| AMP slug | derived from the URL your account returns | ends in `_<tool>`; the prefix is not the slug |
| `MCPServerAdapter` | the server's tool name | sanitized bare name, e.g. `lookup_stock` |

Sanitizing: Unicode folded to ASCII, camelCase split with `_`, lowercased, every non `[a-z0-9_]` character becomes `_`, repeated underscores collapsed, truncated with a hash past 64 characters.

To find a tool in code, resolve the tools and match on the original name:

```python
from crewai import Agent
from crewai.mcp import MCPServerStdio

agent = Agent(role="r", goal="g", backstory="b")
server = MCPServerStdio(command="python", args=["mcp_server.py"])
by_original = {t.original_tool_name: t for t in agent.get_mcp_tools([server])}  # connects now
print(by_original["lookup_stock"].name)       # python_mcp_server.py_lookup_stock (the LLM sees python_mcp_server_py_lookup_stock)
print(by_original["lookup_stock"].run(sku="A-100"))
```

(`mcp_server.py` is any MCP server exposing a `lookup_stock(sku: str)` tool; a FastMCP one is three lines.)

---

## 5. Timeouts, retries, failures

| Path | Connect | Discovery | Per call | Retries on timeout | Down at kickoff |
|---|---|---|---|---|---|
| `MCPServerStdio/HTTP/SSE`, AMP slugs | 30 s | 30 s | 30 s | 3 attempts, 1 s then 2 s backoff; the call is **re-sent** | raises `crewai.mcp.exceptions.MCPConnectionError` |
| `"https://..."` string | 10 s | 15 s (3 tries) | 60 s | 3 attempts; the final error is **returned as text**, not raised | no tools from that ref; run continues (also the case for a healthy server inside a running event loop) |
| `MCPServerAdapter` | `connect_timeout` (default 30) | - | none from crewai | none | `RuntimeError: Failed to initialize MCP Adapter: ...` |

Measured: a stdio tool that sleeps 35 s ran 3 times and failed after ~96 s with `Error executing MCP tool slow_report: Operation timed out after 30 seconds` (direct `tool.run()` raises `RuntimeError`). In a crew with claude-haiku-4-5 the same tool ran 3 times in ~99 s, the agent received `Error executing tool: Error executing MCP tool slow_report: Operation timed out after 30 seconds` as its observation, a tool failure was recorded, and the crew finished normally. The same tool sleeping 65 s behind an `https://` string ran 3 times and returned `MCP tool execution failed after 3 attempts: Connection timed out after 60 seconds` after ~198 s.

None of the native timeouts can be set through a config field or an Agent field in 1.15.22-1.15.23. Design for them:
- Make MCP tools fast (well under 30 s) and idempotent, or split long work into "start job" and "get result" tools.
- Use config objects instead of `https://` strings when a missing server must stop the run.
- Server-side errors (`isError: true`) reach the agent as text and are recorded as `mcp_error` tool failures. `Agent(tool_failure_policy="raise")` turns them into `ToolExecutionFailedError`.

---

## 6. MCPServerAdapter

Needs `uv add "crewai-tools[mcp]"` (installs `mcpadapt`). Without it the constructor prompts `You are missing the 'mcp' package. Would you like to install it? [y/N]`. Under a TTY that blocks forever (verified: still blocked after 20 s). With stdin closed it raises `click.exceptions.Abort`.

```python
from mcp import StdioServerParameters
from crewai import Agent, Crew, Task
from crewai_tools import MCPServerAdapter

stdio = StdioServerParameters(command="python", args=["mcp_server.py"], env={"LOG_LEVEL": "warning"})
# Remote server: pass a dict. Without "transport" the adapter assumes SSE.
remote = {"url": "https://mcp.example.com/mcp", "transport": "streamable-http"}

with MCPServerAdapter(stdio, "lookup_stock", "list_warehouses", connect_timeout=60) as tools:
    agent = Agent(role="Inventory analyst", goal="Check stock", backstory="Careful.", tools=tools)
    task = Task(description="Report stock for A-100", expected_output="One line", agent=agent)
    crew = Crew(agents=[agent], tasks=[task])
    # result = crew.kickoff()     # must run inside the with-block; the server stops on exit
```

- The server starts in the constructor. Positional names after the params filter tools by sanitized name.
- `tools` is a `ToolCollection`: iterate it, index it, or use `tools["lookup_stock"]` / `tools.filter_by_names([...])`.
- Names are the server's own (sanitized), so they are stable across machines. This is the one place a bare MCP tool name is safe to rely on.

### `@CrewBase` integration

```python
from mcp import StdioServerParameters
from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

@CrewBase
class InventoryCrew:
    mcp_server_params = StdioServerParameters(command="python", args=["mcp_server.py"])
    mcp_connect_timeout = 60                      # default 30

    @agent
    def analyst(self) -> Agent:
        return Agent(role="Inventory analyst", goal="Check stock", backstory="Careful.",
                     tools=self.get_mcp_tools("lookup_stock"))   # no names = all tools

    @task
    def check(self) -> Task:
        return Task(description="Check stock for C-3", expected_output="One line", agent=self.analyst())

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks)

# Fresh instance per run: crewai stops the adapter after each kickoff.
# InventoryCrew().crew().kickoff()
```

Reusing one instance for a second kickoff made every MCP call fail with `Event loop is closed` while the crew still reported success (verified).

---

## 7. Local development vs hosted deployment

| Situation | Use |
|---|---|
| Laptop, server is a local script or `npx`/`uvx` package | `MCPServerStdio` |
| Deployed crew, server is Python code you own | `MCPServerStdio(command="python", args=["-m", "<pkg>.server"])` with the module inside `src/<pkg>/` - verified working on CrewAI AMP, as is `MCPServerAdapter` with `crewai-tools[mcp]` in `pyproject.toml` |
| Deployed crew, server runs elsewhere | `MCPServerHTTP` or `MCPServerSSE` pointing at a service reachable from the deployment - not an `https://` string, which yields zero tools on AMP |
| Integration your team connected in CrewAI AMP | `"slug"` / `"slug#tool"` |

- stdio launches the server as a child process of the crew, on whatever machine runs the crew. A laptop path or an `npx` server is not in a deployment; on AMP both made the run fail with `MCPConnectionError`.
- When a deployed run fails with `MCPConnectionError`, `GET /status/{kickoff_id}` was seen to return HTTP 500 `Internal Server Error` on every poll instead of a `FAILED` state. Reproduce locally (`crewai run`) to read the actual error.
- Serve remote MCP over streamable HTTP at a path ending in `/mcp`, on a stable hostname you control, with auth.
- Health check from anywhere: `curl -s -o /dev/null -w "%{http_code}" https://<host>/mcp`. **406** = healthy streamable-HTTP endpoint (a bare GET without the MCP `Accept` header is refused); **404** = wrong path; `000` / connection refused = down.
- Keep credentials out of URL strings. Read them from environment variables into `headers`, and set those variables on the deployment. A stdio server receives a deployment env var only through `env=` (verified on AMP).

---

## 8. Docs that disagree with 1.15.22-1.15.23 code

| Docs say | Code does |
|---|---|
| DSL timeouts: connection 10 s, execution 30 s, discovery 15 s (docs mcp/dsl-integration) | Only the `https://` string path has 10 s/15 s, and its execution limit is 60 s; config objects and slugs use 30/30/30 |
