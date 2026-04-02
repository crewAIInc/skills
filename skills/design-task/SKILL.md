---
name: design-task
description: "CrewAI task design and configuration. Use when creating, configuring, or debugging crewAI tasks — writing descriptions and expected_output, setting up task dependencies with context, configuring output formats (output_pydantic, output_json, output_file), using guardrails for validation, enabling human_input, async execution, markdown formatting, or debugging task execution issues."
---

# CrewAI Task Design Guide

How to write effective tasks that produce reliable, high-quality output from your agents.

---

## The 80/20 Rule

**Spend 80% of your effort on task design, 20% on agent design.** The task is the most important lever you have. A well-designed task with a mediocre agent will outperform a poorly designed task with an excellent agent.

---

## 1. Anatomy of an Effective Task

Every task needs two things: a **description** (what to do and how) and an **expected_output** (what the result looks like).

### Description — The Instructions

A good description includes:
1. **What** to do — the core action
2. **How** to do it — specific steps or approach
3. **Context** — why this matters, what it feeds into
4. **Constraints** — scope limits, things to avoid
5. **Inputs** — what data or context is available

```yaml
research_task:
  description: >
    Conduct thorough research about {topic} for the year {current_year}.

    Your research should:
    1. Identify the top 5 key trends and breakthroughs
    2. For each trend, find at least 2 credible sources
    3. Note any controversies or competing viewpoints
    4. Assess potential industry impact (high/medium/low)

    Focus on developments from the last 6 months.
    Do NOT include speculation or unverified claims.
    The output will feed into a report for {target_audience}.
  expected_output: >
    A structured research brief with 5 sections, one per trend.
    Each section includes: trend name, 2-3 paragraph summary,
    source citations, impact assessment (high/medium/low),
    and a confidence level for your findings.
  agent: researcher
```

### Expected Output — The Success Criteria

The `expected_output` tells the agent what "done" looks like. Be specific about:
- **Format** — bullet points, paragraphs, JSON, table
- **Structure** — sections, headings, order
- **Length** — approximate word count or number of items
- **Quality markers** — citations required, confidence levels, specific fields

| Bad Expected Output | Good Expected Output |
|---|---|
| `A research report` | `A structured brief with 5 sections, each containing: trend name, 2-3 paragraph summary, source citations, and impact rating` |
| `An analysis of the data` | `A markdown table with columns: metric name, current value, 30-day trend, and recommended action. Include at least 10 metrics.` |
| `A blog post` | `A 1000-1500 word technical blog post with: title, introduction, 3-4 main sections with code examples, and a conclusion with next steps` |

---

## 2. The Single Purpose Principle

**One task = one objective.** Never combine multiple operations into a single task.

### Bad: "God Task"

```yaml
# DON'T do this — too many objectives in one task
research_and_write_task:
  description: >
    Research {topic}, analyze the findings, write a blog post,
    and proofread it for grammar errors.
  expected_output: >
    A polished blog post about {topic}.
```

### Good: Focused Tasks

```yaml
research_task:
  description: >
    Research {topic} and identify the top 5 key developments.
  expected_output: >
    A research brief with 5 sections covering key trends.
  agent: researcher

writing_task:
  description: >
    Using the research findings, write a technical blog post about {topic}.
  expected_output: >
    A 1000-1500 word blog post with introduction, main sections,
    and conclusion. Include code examples where relevant.
  agent: writer

editing_task:
  description: >
    Review and edit the blog post for grammar, clarity, and consistency.
  expected_output: >
    The final edited blog post with all corrections applied.
    Include a brief editor's note listing what was changed.
  agent: editor
```

Each task has one clear objective. The sequential flow passes context automatically.

---

## 3. Task Configuration Reference

### Essential Parameters

```python
Task(
    description="...",          # Required: what to do
    expected_output="...",      # Required: what the result looks like
    agent=researcher,           # Optional for hierarchical process; required for sequential
)
```

### Task Dependencies with `context`

```python
analysis_task = Task(
    description="Analyze the research findings...",
    expected_output="...",
    agent=analyst,
    context=[research_task],    # Receives research_task's output as context
)
```

**In sequential process:** Each task auto-receives all prior task outputs. Use `context` only when you need non-linear dependencies.

**In hierarchical process:** `context` is how you create explicit data flow between tasks.

### Structured Output

Use `output_pydantic` or `output_json` when downstream code needs to parse the result:

```python
from pydantic import BaseModel

class ResearchReport(BaseModel):
    trends: list[str]
    confidence: float
    sources: list[str]

research_task = Task(
    description="...",
    expected_output="A structured report with trends, confidence score, and sources.",
    agent=researcher,
    output_pydantic=ResearchReport,   # Agent's output is parsed into this model
)
```

**Important:** `expected_output` is always a **string description** — never a class name. The Pydantic model goes in `output_pydantic`, and the `expected_output` text tells the agent what fields to include.

Access structured output:
```python
result = crew.kickoff(inputs={...})
last_task_output = result.pydantic          # Pydantic model from the last task
all_outputs = result.tasks_output           # List of all TaskOutput objects
first_task = all_outputs[0].pydantic        # Pydantic from a specific task
```

### File Output

```python
Task(
    ...,
    output_file="output/report.md",    # Save output to file
    create_directory=True,             # Create directory if missing (default: True)
)
```

File output and structured output can be combined — the file gets the raw text, and `output_pydantic` gets the parsed model.

### Async Execution

```python
Task(
    ...,
    async_execution=True,     # Run without blocking the next task
)
```

Use for tasks that can run in parallel. The crew continues to the next task while this one executes. Use `context` on downstream tasks to wait for async results.

### Human Review

```python
Task(
    ...,
    human_input=True,         # Pause for human review before finalizing
)
```

When enabled, the agent presents its result and waits for human feedback before marking the task complete. Use for critical outputs that need human approval.

### Markdown Formatting

```python
Task(
    ...,
    markdown=True,            # Add markdown formatting instructions
)
```

Automatically instructs the agent to format output with proper markdown headers, lists, emphasis, and code blocks.

### Callbacks

```python
def log_completion(output):
    print(f"Task completed: {output.description[:50]}...")
    save_to_database(output.raw)

Task(
    ...,
    callback=log_completion,  # Called after task completion
)
```

---

## 4. Task Guardrails — Quality Control

Guardrails validate task output before it passes to the next step. If validation fails, the agent retries.

### Function-Based Guardrails

```python
def validate_word_count(output) -> tuple[bool, Any]:
    """Ensure output is between 500-2000 words."""
    word_count = len(output.raw.split())
    if word_count < 500:
        return (False, f"Output too short ({word_count} words). Expand to at least 500 words.")
    if word_count > 2000:
        return (False, f"Output too long ({word_count} words). Condense to under 2000 words.")
    return (True, output)

Task(
    ...,
    guardrail=validate_word_count,
    guardrail_max_retries=3,       # Max retry attempts (default: 3)
)
```

**Return format:** `(bool, Any)` — first element is pass/fail, second is the result (on success) or error message (on failure).

### LLM-Based Guardrails

```python
Task(
    ...,
    guardrail="Verify the output contains at least 3 source citations and no speculative claims.",
)
```

String guardrails use the agent's LLM to evaluate the output. Good for subjective quality checks.

### Chaining Multiple Guardrails

```python
Task(
    ...,
    guardrails=[
        validate_word_count,           # Function: check length
        validate_no_pii,               # Function: check for PII
        "Ensure the tone is professional and appropriate for a business audience.",  # LLM check
    ],
    guardrail_max_retries=3,
)
```

Guardrails execute sequentially. Each receives the output of the previous guardrail. Mix function-based (deterministic) and LLM-based (subjective) checks.

---

## 5. YAML Configuration (Recommended)

### tasks.yaml

```yaml
research_task:
  description: >
    Conduct thorough research about {topic} for {current_year}.
    Identify key trends, breakthrough technologies,
    and potential industry impacts.
    Focus on the last 6 months of developments.
  expected_output: >
    A structured research brief with 5 sections.
    Each section: trend name, 2-3 paragraph summary,
    source citations, and impact assessment.
  agent: researcher

analysis_task:
  description: >
    Analyze the research findings and create actionable recommendations
    for {target_audience}.
  expected_output: >
    A prioritized list of 5 recommendations with:
    rationale, estimated effort, and expected impact.
  agent: analyst
  context:
    - research_task

report_task:
  description: >
    Compile a final report combining research and analysis for {target_audience}.
  expected_output: >
    A polished markdown report with executive summary,
    detailed findings, recommendations, and appendices.
  agent: writer
  output_file: output/report.md
```

### Wiring in crew.py

```python
@CrewBase
class ResearchCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["analysis_task"],
            context=[self.research_task()],
        )

    @task
    def report_task(self) -> Task:
        return Task(
            config=self.tasks_config["report_task"],
            output_file="output/report.md",
        )
```

**Critical:** The method name (`def research_task`) must match the YAML key (`research_task:`).

---

## 6. Task Dependencies and Context Flow

### Sequential Process (Default)

In `Process.sequential`, tasks run in order. Each task automatically receives all prior task outputs as context.

```
research_task → analysis_task → report_task
     ↓               ↓              ↓
  output 1    output 1 + 2    output 1 + 2 + 3
```

You don't need `context=` in sequential — it's implicit. Use it only to create non-linear dependencies:

```python
# Task C depends on A but NOT B
task_c = Task(
    ...,
    context=[task_a],  # Only receives task_a output, not task_b
)
```

### Explicit Dependencies

```python
# Diamond dependency pattern
task_a = Task(...)                          # Entry point
task_b = Task(..., context=[task_a])        # Depends on A
task_c = Task(..., context=[task_a])        # Also depends on A
task_d = Task(..., context=[task_b, task_c])  # Depends on both B and C
```

### Conditional Tasks

```python
from crewai.task import ConditionalTask

def needs_more_data(output) -> bool:
    return len(output.pydantic.items) < 10

extra_research = ConditionalTask(
    description="Fetch additional data sources...",
    expected_output="...",
    agent=researcher,
    condition=needs_more_data,  # Only runs if previous output has < 10 items
)
```

---

## 7. Task Tools

Tasks can have their own tools that override the agent's default tools for that specific task:

```python
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

Task(
    description="Search for and scrape the top 5 articles about {topic}...",
    expected_output="...",
    agent=researcher,
    tools=[SerperDevTool(), ScrapeWebsiteTool()],  # Task-specific tools
)
```

**When to use task-level tools:**
- The task needs tools the agent doesn't normally have
- You want to restrict an agent to specific tools for this task
- Different tasks by the same agent need different tool sets

---

## 8. Variable Interpolation

Use `{variable}` placeholders in YAML for reusable tasks:

```yaml
research_task:
  description: >
    Research {topic} trends for {current_year},
    targeting {target_audience}.
  expected_output: >
    A report on {topic} suitable for {target_audience}.
```

Variables are replaced when you call `crew.kickoff(inputs={...})`:

```python
crew.kickoff(inputs={
    "topic": "AI Agents",
    "current_year": "2025",
    "target_audience": "developers",
})
```

**Common mistakes:**
- Missing variable in `inputs` → literal `{variable}` appears in the prompt
- Using `{{ }}` Jinja2 syntax → crewAI uses single braces `{ }`
- Unused variables in `inputs` → silently ignored (no error)

---

## 9. Common Task Design Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| Vague description ("Research the topic") | Agent produces shallow, unfocused output | Add specific steps, constraints, and context |
| Vague expected_output ("A report") | Agent guesses at format and structure | Specify format, sections, length, quality markers |
| Multiple objectives in one task | Agent does all of them poorly | Split into focused single-purpose tasks |
| No context between dependent tasks | Agent lacks information from prior steps | Use `context=[prior_task]` for explicit dependencies |
| `expected_output` references a Pydantic class | Agent sees a class name string, not field names | Keep `expected_output` as a human-readable string; use `output_pydantic` for the model |
| Missing tools for data tasks | Agent fabricates data instead of fetching it | Add tools to the task or agent |
| No guardrails on critical output | Bad output flows downstream unchecked | Add function or LLM guardrails |
| Overly strict expected_output | Agent loops trying to match impossible criteria | Be specific but achievable; lower `guardrail_max_retries` to fail faster |
| Description duplicates backstory | Wasted tokens and confused agent | Description = what to do; backstory = who you are |

---

## 10. Task Design Checklist

Before running a task, verify:

- [ ] **Description** includes what, how, context, and constraints
- [ ] **Expected output** specifies format, structure, and quality markers
- [ ] **Single purpose** — one clear objective per task
- [ ] **Agent assigned** (or task is in a hierarchical crew)
- [ ] **Dependencies** set via `context` where needed
- [ ] **Tools** provided for any task requiring external data
- [ ] **Structured output** configured if downstream code parses the result
- [ ] **Guardrails** set for critical outputs
- [ ] **Variables** in YAML match the `inputs` dict keys
- [ ] **Expected output is achievable** — test with a simple run before adding complexity

---

## References

For deeper dives into specific topics, see:

- [Structured Output](references/structured-output.md) — `output_pydantic`, `output_json`, and `response_format` patterns across LLM, Agent, Task, and Crew levels

For related skills:

- **getting-started** — project scaffolding, choosing the right abstraction, Flow architecture
- **design-agent** — agent Role-Goal-Backstory framework, parameter tuning, tool assignment, memory & knowledge configuration
- **ask-docs** — query the live CrewAI documentation MCP server for questions not covered by these skills
