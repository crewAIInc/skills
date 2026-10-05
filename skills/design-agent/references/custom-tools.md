# Custom Tools Reference

How to build your own tools for crewAI agents. The **connect-tools-and-mcp** skill has the full, verified reference (failure policy, usage limits, MCP); this page covers the basics for agent design.

---

## Method 1: @tool Decorator (Simple)

Best for quick, single-function tools.

```python
from crewai.tools import tool

@tool("Search Database")
def search_database(query: str) -> str:
    """Search the internal database for relevant records."""
    results = db.search(query)
    return "\n".join(str(r) for r in results)
```

The docstring becomes the tool's description - make it clear so the agent knows when to use it. A function without a docstring raises `ValueError: Function must have a docstring`. The name is offered to the LLM sanitized (`"Search Database"` becomes `search_database`).

### With Multiple Parameters

```python
@tool("Filter Records")
def filter_records(category: str, min_score: int = 0) -> str:
    """Filter database records by category and minimum score."""
    results = db.filter(category=category, min_score=min_score)
    return "\n".join(str(r) for r in results)
```

---

## Method 2: BaseTool Subclass (Full Control)

Best for tools with configuration, state, or complex input schemas.

```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    """Input schema for the database search tool."""
    query: str = Field(..., description="The search query string")
    limit: int = Field(default=10, description="Max results to return")

class DatabaseSearchTool(BaseTool):
    name: str = "Search Database"
    description: str = "Search the internal database for relevant records. Use when you need to find specific data."
    args_schema: type[BaseModel] = SearchInput

    # Add custom configuration as class attributes
    db_connection: str = ""

    def _run(self, query: str, limit: int = 10) -> str:
        results = db.search(query, limit=limit)
        return "\n".join(str(r) for r in results)
```

**Key points:**
- `name` — shown to the agent in tool selection
- `description` — critical for agent to know WHEN to use the tool
- `args_schema` — Pydantic model defining inputs (enables validation and descriptions)
- `_run()` - the actual tool logic; parameter names must match the schema fields. It is required: a subclass without `_run` cannot be instantiated

Import `BaseTool` and `tool` from `crewai.tools`, not `crewai_tools` (that raises `ImportError`).

---

## Async Tools

For I/O-bound operations (API calls, web requests), make the function itself async:

```python
import aiohttp
from crewai.tools import tool

@tool("Fetch Webpage")
async def fetch_webpage(url: str) -> str:
    """Fetch and return the text content of a webpage."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()
```

For a `BaseTool`, put the async code in `async def _run(...)`. Agents call a tool through `_run` in both `kickoff()` and `akickoff()`. An `_arun` override is only used when you call `tool.arun()` yourself (verified: the agent-side invocation of a tool with both methods ran `_run`).

---

## Custom Caching

Tool-result caching is **off by default**: turn it on with `Crew(cache=True)`. Then control per call what may be cached:

```python
@tool("Expensive Lookup")
def expensive_lookup(query: str) -> str:
    """Look up data from an expensive external API."""
    return api.query(query)

def should_cache(arguments: dict, result: str) -> bool:
    """Only cache successful, non-empty results."""
    return len(result) > 0 and "error" not in result.lower()

expensive_lookup.cache_function = should_cache
```

Never cache live-data or state-changing tools.

---

## Tool Assignment

Tools can be assigned at the **agent level** or the **task level**:

```python
# Agent-level: available for ALL tasks this agent performs
agent = Agent(
    role="Researcher",
    goal="...",
    backstory="...",
    tools=[SerperDevTool(), search_database],
)

# Task-level: REPLACES the agent's tools for this specific task
task = Task(
    description="Search the database for...",
    expected_output="...",
    agent=agent,
    tools=[search_database],  # Only this tool available for this task
)
```

Verified live: an agent holding a weather tool, given a task with only a population tool, could call only the population tool.

---

## Best Practices

1. **Write clear descriptions** — the agent uses the description to decide when to use the tool
2. **Use Pydantic schemas** for complex inputs — gives agents parameter descriptions and validation
3. **Return strings** — tool output is fed back into the LLM as text
4. **Make failures visible** - a raised exception is fed back to the agent and the crew still "succeeds". When downstream code must know, return `ToolFailure(...)` and set `tool_failure_policy="raise"` (see **connect-tools-and-mcp**)
5. **Keep tools focused** — one tool per action, not one tool that does everything
6. **Limit tools per agent** — 3-5 tools max; too many tools confuses the agent
