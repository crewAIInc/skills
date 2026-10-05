# Structured Output Reference

How to get structured, typed output from LLM calls, agents, tasks, and crews.

Verified against crewai 1.15.22 and 1.15.23 on 2026-10-01, live with a real LLM. The parameter name differs by level - `response_model` on `LLM.call()`, `response_format` on `Agent.kickoff()` and the `LLM(...)` constructor, `output_pydantic` / `output_json` on `Task` - and a wrong name on `Task` is silently ignored.

---

## The Four Levels

Structured output works differently at each abstraction level:

| Level | Parameter | Returns | Access Pattern |
|---|---|---|---|
| `LLM.call()` | `response_model=Model` | Pydantic object directly | `result.field` |
| `Agent.kickoff()` | `response_format=Model` | `LiteAgentOutput` wrapper | `result.pydantic.field` |
| `Task` | `output_pydantic=Model` | `TaskOutput` wrapper | `task.output.pydantic.field` |
| `Crew.kickoff()` | (via last task) | `CrewOutput` wrapper | `result.pydantic.field` |

---

## 1. LLM.call() - Direct Pydantic Return

```python
from crewai import LLM
from pydantic import BaseModel

class Sentiment(BaseModel):
    label: str       # "positive", "negative", "neutral"
    confidence: float
    reasoning: str

llm = LLM(model="openai/gpt-4o")
text = "I love this product, it works perfectly."

result = llm.call(
    messages=[{"role": "user", "content": f"Analyze sentiment: {text}"}],
    response_model=Sentiment,          # NOT response_format - that raises TypeError here
)

# Returns Pydantic object DIRECTLY
print(result.label)       # "positive"
print(result.confidence)  # 0.95
```

`llm.call(..., response_format=Sentiment)` raises `TypeError: ...call() got an unexpected keyword argument 'response_format'. Did you mean 'response_model'?`. To make structured output the default for every call, set it on the constructor instead: `LLM(model=..., response_format=Sentiment).call("...")` also returns a `Sentiment`.

---

## 2. Agent.kickoff() - LiteAgentOutput Wrapper

```python
from crewai import Agent
from pydantic import BaseModel

class ResearchFindings(BaseModel):
    main_points: list[str]
    sources: list[str]
    confidence: float

researcher = Agent(
    role="Researcher",
    goal="Research topics thoroughly",
    backstory="...",
    llm="openai/gpt-4o",
)

result = researcher.kickoff(
    "Research the latest AI developments",
    response_format=ResearchFindings,
)

# Returns LiteAgentOutput - access via .pydantic
# Agent.kickoff takes response_format (response_model raises TypeError here)
print(result.pydantic.main_points)   # list[str]
print(result.pydantic.sources)       # list[str]
print(result.raw)                    # Raw string output
print(result.usage_metrics)          # Token usage dict
```

---

## 3. Task - output_pydantic / output_json

### output_pydantic

```python
from pydantic import BaseModel
from crewai import Task

class BlogPost(BaseModel):
    title: str
    content: str
    tags: list[str]

task = Task(
    description="Write a blog post about {topic}",
    expected_output="A blog post with title, content, and relevant tags.",  # Always a string!
    agent=writer,
    output_pydantic=BlogPost,          # set in Python, never in tasks.yaml
)
```

**Access after crew runs:**
```python
result = crew.kickoff(inputs={"topic": "AI"})

# From CrewOutput (last task)
result.pydantic.title       # str
result.pydantic.tags        # list[str]

# From specific task output
task_output = result.tasks_output[0]
task_output.pydantic.title  # str
task_output.raw             # Raw string
```

### output_json

```python
task = Task(
    description="Write a blog post about {topic}",
    expected_output="A JSON object with title, content, and tags fields.",
    agent=writer,
    output_json=BlogPost,  # Uses same Pydantic model to define schema
)
```

**Access:**
```python
result = crew.kickoff(inputs={"topic": "AI"})

result.json_dict            # dict - parsed JSON
result.json_dict["title"]   # str
```

### Key Difference

- `output_pydantic` → validated Pydantic model instance → access via `.pydantic`
- `output_json` → parsed dict from JSON string → access via `.json_dict`
- Both use a Pydantic model to define the schema
- `expected_output` is always a human-readable string, never a class reference
- With `output_file` set, the file receives the JSON of the model/dict, not the agent's prose
- `Task(response_model=Model)` also exists, but it only asks the provider for native structured output: the JSON lands in `.raw` and `.pydantic` stays `None`. Use `output_pydantic`.

---

## 4. Crew.kickoff() - CrewOutput

The crew's output comes from the **last task** in the sequence:

```python
result = crew.kickoff(inputs={"topic": "AI"})

# Last task's output
result.raw                  # str - always available
result.pydantic             # Pydantic model (if last task has output_pydantic, else None)
result.json_dict            # dict (if last task has output_json, else None)
result["title"]             # reads from pydantic / json_dict

# All task outputs
result.tasks_output         # list[TaskOutput]
result.tasks_output[0].raw  # First task's raw output
result.tasks_output[1].pydantic  # Second task's structured output

# Token usage
result.token_usage          # UsageMetrics
```

---

## Pydantic Model Design Tips

### Keep Models Simple

```python
# Good - flat, clear fields
class Report(BaseModel):
    title: str
    summary: str
    key_findings: list[str]
    confidence: float

# Bad - too nested, LLM struggles
class Report(BaseModel):
    metadata: Metadata
    sections: list[Section]
    analysis: Analysis
    recommendations: list[Recommendation]
```

### Use Field Descriptions

```python
from pydantic import BaseModel, Field

class Report(BaseModel):
    title: str = Field(description="A concise, descriptive title")
    findings: list[str] = Field(description="List of 3-5 key findings")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
```

Field descriptions help the LLM understand what each field expects.

### Provide Defaults for Optional Fields

```python
class Analysis(BaseModel):
    summary: str
    risk_level: str = "medium"           # Default if LLM omits
    sources: list[str] = []              # Default empty list
    notes: str | None = None             # Explicitly optional
```

---

## Common Pitfalls

| Mistake | Fix |
|---|---|
| `expected_output="BlogPost"` (class name) | Use a descriptive string: `"A blog post with title, content, and tags"` |
| Accessing `result.title` on CrewOutput | Use `result.pydantic.title` (or `result["title"]`) - output is wrapped |
| Deeply nested Pydantic models | Flatten the model - LLMs struggle with deep nesting |
| Mixing `output_pydantic` and `output_json` on same task | Pick one - setting both raises `Only one output type can be set` |
| `llm.call(..., response_format=Model)` | Use `response_model=Model`; without either, `LLM.call()` returns a plain string |
| `Task(response_format=Model)` | Silently ignored - use `output_pydantic=Model` |
| `output_pydantic: Model` in `tasks.yaml` | `KeyError`, or silently dropped - set it in the `@task` method in Python |
| `result.pydantic is None` after a "successful" run | Check the task really has `output_pydantic`; assert non-None at the boundary |
| Parsing fails on a complex model | Simplify the model or use a more capable LLM |
