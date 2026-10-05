# Custom Tools Reference

Runnable patterns for custom crewAI tools on crewai 1.15.22-1.15.23: `BaseTool`, `@tool`, async, failures, caching and usage limits.

---

## 1. BaseTool with an args_schema

```python
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class SearchInput(BaseModel):
    """Arguments the LLM must supply."""
    query: str = Field(..., description="Keywords to search the catalog for")
    limit: int = Field(5, description="Maximum number of results")

class CatalogSearchTool(BaseTool):
    name: str = "search_catalog"
    description: str = (
        "Search the product catalog by keyword. Use when the user asks "
        "whether a product exists or what it costs."
    )
    args_schema: type[BaseModel] = SearchInput

    # Configuration is just more pydantic fields; set them at construction.
    catalog_name: str = "default"

    def _run(self, query: str, limit: int = 5) -> str:
        return f"{limit} results for {query!r} in {self.catalog_name}"

tool = CatalogSearchTool(catalog_name="spring-2026")
print(tool.run(query="mug", limit="3"))     # "3" is coerced to int by the schema
try:
    tool.run(limit=2)                       # missing required 'query'
except ValueError as e:
    print(str(e).splitlines()[0])           # Tool 'search_catalog' arguments validation failed: ...
```

- `_run` parameter names must match the schema field names.
- Without `args_schema`, crewai infers one from the `_run` signature.
- The LLM sees `Tool Name`, `Tool Arguments` (the JSON schema, including your `Field` descriptions) and `Tool Description`. Spend your words on the descriptions.

---

## 2. The @tool decorator

```python
from crewai.tools import tool

@tool
def word_count(text: str) -> int:
    """Count the words in a text."""
    return len(text.split())

@tool("Unit Converter")
def convert(km: float) -> str:
    """Convert kilometres to miles."""
    return f"{km * 0.621371:.1f} mi"

@tool("Final Report", result_as_answer=True)
def final_report(topic: str) -> str:
    """Produce the final report for a topic."""
    return f"REPORT on {topic}"

@tool("Send Invoice", max_usage_count=1)
def send_invoice(customer_id: str) -> str:
    """Send one invoice to a customer."""
    return f"invoice sent to {customer_id}"

print(word_count.name, convert.name)    # word_count Unit Converter
print(convert.run(km=10))               # 6.2 mi
```

- `@tool(*args, result_schema=None, result_as_answer=False, max_usage_count=None)` is the full signature. The function name, or the string you pass, becomes the name.
- The docstring is required and becomes the description. Without one you get `ValueError: Function must have a docstring`.
- In the prompt the name is sanitized: `Unit Converter` is offered as `unit_converter`.

---

## 3. Async tools

Agents execute every tool through `_run`, in both `crew.kickoff()` and `await crew.akickoff()`. An `_arun` override is only called when you invoke `tool.arun(...)` directly. To make an agent-facing tool async, make `_run` itself a coroutine:

```python
import asyncio
from crewai.tools import BaseTool, tool

class FetchPageTool(BaseTool):
    name: str = "fetch_page"
    description: str = "Fetch a web page and return its HTML."

    async def _run(self, url: str) -> str:
        await asyncio.sleep(0)            # stand-in for an async HTTP call
        return f"<html>{url}</html>"

@tool("Ping")
async def ping(host: str) -> str:
    """Ping a host."""
    await asyncio.sleep(0)
    return f"pong from {host}"

print(FetchPageTool().run(url="a.example"))   # works from sync code too
print(ping.run(host="db"))
```

A `BaseTool` that defines only `_arun` cannot be instantiated: `_run` is abstract (`TypeError: Can't instantiate abstract class ...`).

---

## 4. Reporting failures

A tool that raises does **not** fail the crew. crewai catches the exception, feeds the message to the agent as the observation, and records a tool failure. Then the agent usually writes a confident final answer. Make failures explicit:

```python
from crewai import Agent, Crew, Task
from crewai.tools import BaseTool, ToolFailure, ToolExecutionFailedError

class InventoryApiTool(BaseTool):
    name: str = "inventory_api"
    description: str = "Query the inventory API for a SKU."

    def _run(self, sku: str) -> ToolFailure | str:
        status = 429                                  # pretend the API rate-limited us
        if status != 200:
            return ToolFailure(message=f"inventory API returned {status}",
                               code="rate_limited", retryable=True)
        return "42 units"

agent = Agent(role="Analyst", goal="Check stock", backstory="Careful.",
              tools=[InventoryApiTool()],
              tool_failure_policy="raise")            # "ignore" | "warn" (default) | "raise"
task = Task(description="Check stock for A-100", expected_output="Stock level", agent=agent)
crew = Crew(agents=[agent], tasks=[task])
# crew.kickoff() now raises ToolExecutionFailedError instead of finishing "successfully".
```

| Policy | Behaviour (verified) |
|---|---|
| `warn` (default) | Failure is recorded in `result.tasks_output[i].tool_failures` and an event is emitted; the agent sees `inventory API returned 429 (code: rate_limited)` and continues |
| `raise` | Same, then the run aborts with `ToolExecutionFailedError: Tool 'inventory_api' failed during '...'` |
| `ignore` | Nothing recorded |

`tool_failure_policy` exists on `BaseTool`, `Agent`, `Task` and `Crew`. The most specific setting wins: tool, then task, then agent, then crew.

---

## 5. Caching

```python
from crewai import Agent, Crew, Task
from crewai.tools import BaseTool

class QuoteTool(BaseTool):
    name: str = "fx_quote"
    description: str = "Live FX quote for a currency pair."
    def _run(self, pair: str) -> str:
        return f"{pair} 1.0842"

live = QuoteTool(cache_function=lambda args, result: False)   # never cache live data
agent = Agent(role="Analyst", goal="Quote FX", backstory="Precise.", tools=[live])
crew = Crew(
    agents=[agent],
    tasks=[Task(description="Quote EURUSD", expected_output="A rate", agent=agent)],
    cache=True,      # opt-in in 1.15.3+; default False
)
```

Measured with a call sequence A, B, A:

| Configuration | Tool executions |
|---|---|
| `Crew()` (default) | 3 |
| `Crew(cache=True)` | 2 |
| `Crew(cache=True)` + `cache_function` returning `False` | 3 |
| `Crew(cache=True)` + `Agent(cache=False)` | 3 |

The same call twice *in a row* executes once in every configuration. That is the repeated-input guard, not the cache.

---

## 6. Usage limits and result_as_answer

```python
from crewai.tools import BaseTool

class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = "Send the drafted email. Only once per task."
    max_usage_count: int | None = 1
    def _run(self, to: str, body: str) -> str:
        return f"sent to {to}"

t = SendEmailTool()
print(t.run(to="ops@example.com", body="hi"))
print(t.run(to="ops@example.com", body="again"))   # ToolFailure: ... reached its usage limit of 1 times ...
t.reset_usage_count()
```

- Inside a crew the limit applies **per task execution**. With `max_usage_count=1` and one tool instance, two tasks in one kickoff each ran the tool once, and a later kickoff ran it again. A direct `tool.run()` counts on the instance until `reset_usage_count()`. For a hard "once per run" or "once ever" rule (payments, emails), enforce it in your own code or state.
- `result_as_answer=True` makes the tool's return value the task's raw output. The agent's next message is never requested (verified: 1 LLM call).

---

## 7. Assigning tools

| Where | Effect |
|---|---|
| `Agent(tools=[...])` | Available for every task the agent runs |
| `Task(tools=[...])` | Replaces the agent's tools for that task (verified: agent tools absent from the prompt) |
| `Agent(mcps=[...])` | MCP tools are added at execution time, see [mcp-connections.md](mcp-connections.md) |
