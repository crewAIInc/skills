# Custom Tools Reference

How to build your own tools for crewAI agents.

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

The docstring becomes the tool's description — make it clear so the agent knows when to use it.

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
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    """Input schema for the database search tool."""
    query: str = Field(..., description="The search query string")
    limit: int = Field(default=10, description="Max results to return")

class DatabaseSearchTool(BaseTool):
    name: str = "Search Database"
    description: str = "Search the internal database for relevant records. Use when you need to find specific data."
    args_schema: Type[BaseModel] = SearchInput

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
- `_run()` — the actual tool logic; parameter names must match the schema fields

---

## Async Tools

For I/O-bound operations (API calls, web requests):

### With @tool Decorator

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

### With BaseTool (Both Sync and Async)

```python
class WebFetcherTool(BaseTool):
    name: str = "Fetch Webpage"
    description: str = "Fetch content from a URL"
    args_schema: Type[BaseModel] = WebFetcherInput

    def _run(self, url: str) -> str:
        """Sync fallback."""
        import requests
        return requests.get(url).text

    async def _arun(self, url: str) -> str:
        """Async implementation — preferred when available."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.text()
```

---

## Custom Caching

Control when tool results are cached:

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

# Task-level: available ONLY for this specific task (overrides agent tools)
task = Task(
    description="Search the database for...",
    expected_output="...",
    agent=agent,
    tools=[search_database],  # Only this tool available for this task
)
```

---

## Best Practices

1. **Write clear descriptions** — the agent uses the description to decide when to use the tool
2. **Use Pydantic schemas** for complex inputs — gives agents parameter descriptions and validation
3. **Return strings** — tool output is fed back into the LLM as text
4. **Handle errors gracefully** — return error messages as strings rather than raising exceptions
5. **Keep tools focused** — one tool per action, not one tool that does everything
6. **Limit tools per agent** — 3-5 tools max; too many tools confuses the agent
