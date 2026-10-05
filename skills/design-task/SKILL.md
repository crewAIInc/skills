---
name: design-task
description: "CrewAI task design and configuration. Use when creating, configuring, or debugging crewAI tasks — writing descriptions and expected_output, setting up task dependencies with context, configuring output formats (output_pydantic, output_json, output_file), using guardrails for validation, enabling human_input, async execution, markdown formatting, or debugging task execution issues."
---

# CrewAI Task Design Guide

How to write effective tasks that produce reliable, high-quality output from your agents.

Verified against crewai 1.15.23 on 2026-10-01.
Live-tested with real LLMs on 2026-10-01.
For exact current API forms (imports, parameter names, structured output, guardrail signatures) the **check-crewai-api** skill is the reference; where this skill and it disagree, follow check-crewai-api.

---

**The 80/20 rule: spend 80% of your effort on task design, 20% on agent design.** The task is the most important lever you have. A well-designed task with a mediocre agent will outperform a poorly designed task with an excellent agent.

---

## 1. Anatomy of an Effective Task

Every task needs two things: a **description** (what to do and how) and an **expected_output** (what the result looks like). Both are required - `Task(description=...)` alone raises `ValidationError ... expected_output Field required`.

### Description - The Instructions

A good description includes:
1. **What** to do - the core action
2. **How** to do it - specific steps or approach
3. **Context** - why this matters, what it feeds into
4. **Constraints** - scope limits, things to avoid
5. **Inputs** - what data or context is available

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

### Expected Output - The Success Criteria

The `expected_output` tells the agent what "done" looks like. Be specific about:
- **Format** - bullet points, paragraphs, JSON, table
- **Structure** - sections, headings, order
- **Length** - approximate word count or number of items
- **Quality markers** - citations required, confidence levels, specific fields

| Bad Expected Output | Good Expected Output |
|---|---|
| `A research report` | `A structured brief with 5 sections, each containing: trend name, 2-3 paragraph summary, source citations, and impact rating` |
| `An analysis of the data` | `A markdown table with columns: metric name, current value, 30-day trend, and recommended action. Include at least 10 metrics.` |
| `A blog post` | `A 1000-1500 word technical blog post with: title, introduction, 3-4 main sections with code examples, and a conclusion with next steps` |

---

## 2. The Single Purpose Principle

**One task = one objective.** Never combine multiple operations into a single task.

```yaml
# DON'T - a "god task" with four objectives
research_and_write_task:
  description: >
    Research {topic}, analyze the findings, write a blog post,
    and proofread it for grammar errors.
  expected_output: >
    A polished blog post about {topic}.

# DO - focused tasks, one objective each
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
    A 1000-1500 word blog post with introduction, main sections, and conclusion.
  agent: writer
# ...and an editing_task with agent: editor
```

Each task has one clear objective. The sequential flow passes context automatically.

---

## 3. Task Configuration Reference

### Essential Parameters

```python
Task(description="...", expected_output="...", agent=researcher)  # agent: required for sequential, optional for hierarchical
```

A sequential crew with an agent-less task fails at `Crew(...)`: `Sequential process error: Agent is missing in the task ...`.

### Task Dependencies with `context`

```python
analysis_task = Task(description="Analyze the research findings...", expected_output="...",
                     agent=analyst, context=[research_task])  # receives only research_task's output
```

The rule is the same in sequential and hierarchical crews:
- **No `context`** - the task receives the raw output of every task that ran before it.
- **`context=[a, b]`** - the task receives only those tasks' outputs.
- **`context=[]`** - the task receives no prior output at all.

A `context` entry must be an earlier task in the crew; pointing at a later task fails at `Crew(...)` ("context dependency on a future task").

### Structured Output

Use `output_pydantic` or `output_json` when downstream code needs to parse the result:

```python
from pydantic import BaseModel

class ResearchReport(BaseModel):
    trends: list[str]
    confidence: float
    sources: list[str]

research_task = Task(description="...", agent=researcher,
                     expected_output="A structured report with trends, confidence score, and sources.",
                     output_pydantic=ResearchReport)   # agent's output is parsed into this model
```

**Important:** `expected_output` is always a **string description** - never a class name. The Pydantic model goes in `output_pydantic`, and the `expected_output` text tells the agent what fields to include. Set only one of `output_pydantic` / `output_json` (both raises `Only one output type can be set`).

Access structured output:
```python
result = crew.kickoff(inputs={...})
last_task_output = result.pydantic          # Pydantic model from the LAST task (None if it has no output_pydantic)
all_outputs = result.tasks_output           # List of all TaskOutput objects
first_task = all_outputs[0].pydantic        # Pydantic from a specific task
assert first_task is not None, "structured output was dropped"
```

Set `output_pydantic` in Python, not in `tasks.yaml` (section 5). Not `Task(response_format=...)` (silently ignored) or `Task(response_model=...)` (`.pydantic` stays `None`). More: [structured-output.md](references/structured-output.md).

### File Output

`Task(..., output_file="output/report.md")` saves the output; `create_directory` (default `True`) creates missing directories. What gets written depends on the output type: the raw text for a plain task, but **the JSON of the model** when `output_pydantic` or `output_json` is set (even if the file is named `.md`). If you want a human-readable file from a structured task, add a separate formatting task without a model and give it the `output_file`.

### Async Execution

```python
pros = Task(..., agent=analyst, async_execution=True)
cons = Task(..., agent=critic, async_execution=True)    # a DIFFERENT agent
verdict = Task(..., agent=analyst, context=[pros, cons])
crew = Crew(agents=[analyst, critic], tasks=[pros, cons, verdict])
```

Async tasks start without waiting; consecutive async tasks run concurrently. The next synchronous task waits for every pending async task before it starts, and (with no `context`) sees all their outputs; give it `context=[...]` to choose which.

Rules, all enforced:
- **Give each concurrently running async task its own agent.** Two async tasks on the same agent fail at kickoff with `RuntimeError: Executor is already running. Cannot invoke the same executor instance concurrently.`
- A crew may end with at most one async task (`The crew must end with at most one asynchronous task`) - finish with a synchronous task that gathers the results.
- An async task cannot list an async task from the same concurrent run in its own `context`, and a `ConditionalTask` cannot be async.

### Human Review

`Task(..., human_input=True)` pauses for human review before finalizing. The agent produces its answer, then the terminal shows a "Human Feedback Required" panel and reads a line from stdin. Typing feedback makes the agent revise and ask again; an empty line (Enter) accepts the answer. Use for critical outputs that need human approval.

It needs an interactive stdin. In CI, a server, or any run with stdin closed, `input()` raises `EOFError` - after the agent's retries, so you also pay for the extra LLM calls. To drive it from a script, pipe the answers in: `printf 'Make it shorter.\n\n' | python run.py` (one feedback round, then accept). For approval steps that cannot rely on a terminal, see Flow `@human_feedback` in the **build-flow** skill.

**Do not use `human_input=True` or Flow `@human_feedback` to model normal follow-up chat.** In conversational Flows, the next user line should be another `flow.handle_turn(message, session_id=...)` call. Human review is for approving or correcting a specific task/step output before it moves downstream.

### Markdown Formatting

`Task(..., markdown=True)` appends an instruction to the task prompt that the final answer MUST be Markdown (headers, bold/italic, bullet lists, code spans and fenced code blocks).

### Callbacks

```python
def log_completion(output: TaskOutput) -> None:   # from crewai import TaskOutput
    print(f"Task completed: {output.description[:50]}...")

Task(..., callback=log_completion)  # called with the TaskOutput after the task and its guardrails finish
```

---

## 4. Task Guardrails - Quality Control

Guardrails validate task output before it passes to the next step. If validation fails, the error is fed back to the agent and the task retries, up to `guardrail_max_retries` (default 3). After that the task raises `Task failed guardrail validation after N retries. Last error: ...`.

### Function-Based Guardrails

```python
from typing import Any

from crewai import Task, TaskOutput


def validate_word_count(output: TaskOutput) -> tuple[bool, Any]:
    """Ensure output is between 500-2000 words."""
    word_count = len(output.raw.split())
    if word_count < 500:
        return (False, f"Output too short ({word_count} words). Expand to at least 500 words.")
    if word_count > 2000:
        return (False, f"Output too long ({word_count} words). Condense to under 2000 words.")
    return (True, output)

Task(..., guardrail=validate_word_count, guardrail_max_retries=3)  # max retries (default: 3)
```

**Return format:** `(bool, Any)` - first element is pass/fail, second is the result on success (the `TaskOutput`, or a string that replaces `output.raw`; never `None`) or the error message on failure. Annotate the return as `tuple[bool, Any]` or leave it unannotated: `-> bool` raises `If return type is annotated, it must be Tuple[bool, Any]` at `Task(...)`. Use `guardrail_max_retries`, not the deprecated `max_retries`.

### LLM-Based Guardrails

```python
Task(..., agent=writer, guardrail="Verify the output contains at least 3 source citations and no speculative claims.")
```

A string guardrail is checked by an extra LLM call made with the task agent's LLM. Good for subjective quality checks. It needs the task to have an `agent`, or `Task(...)` raises `Agent is required to use non-programmatic guardrails`.

### Chaining Multiple Guardrails

```python
def validate_no_pii(output: TaskOutput) -> tuple[bool, Any]:
    if "@" in output.raw:
        return (False, "Remove email addresses.")
    return (True, output)

Task(..., guardrails=[
    validate_word_count,           # Function: check length
    validate_no_pii,               # Function: check for PII
    "Ensure the tone is professional and appropriate for a business audience.",  # LLM check
])
```

Guardrails execute sequentially. Each receives the output of the previous guardrail (a string result replaces `output.raw` for the next one). Mix function-based (deterministic) and LLM-based (subjective) checks. If you set both `guardrails=[...]` and `guardrail=`, only the list is used.

---

## 5. YAML Configuration (Recommended)

### tasks.yaml

```yaml
research_task:            # full description/expected_output as in section 1
  description: >
    Conduct thorough research about {topic} for {current_year}.
  expected_output: >
    A structured research brief with 5 sections.
  agent: researcher

analysis_task:
  description: >
    Analyze the research findings and recommend actions for {target_audience}.
  expected_output: >
    A prioritized list of 5 recommendations with rationale and expected impact.
  agent: analyst
  context:
    - research_task

report_task:
  description: >
    Compile a final report combining research and analysis for {target_audience}.
  expected_output: >
    A polished markdown report with executive summary, findings and recommendations.
  agent: writer
  output_file: output/report.md
```

### Wiring in crew.py

```python
from pydantic import BaseModel

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

class Recommendations(BaseModel):
    items: list[str]

@CrewBase
class ResearchCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # @agent methods researcher, analyst, writer omitted

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def analysis_task(self) -> Task:
        # context and agent come from YAML; the model class must be set here in Python
        return Task(config=self.tasks_config["analysis_task"], output_pydantic=Recommendations)

    @task
    def report_task(self) -> Task:
        return Task(config=self.tasks_config["report_task"])   # output_file comes from YAML

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks)
```

**Keep method names identical to YAML keys.** YAML `context:` entries are resolved by calling the `@task` method of that name, and `agent:` by the `@agent` method of that name, so a mismatch fails when the crew is built. `description`, `expected_output`, `agent`, `context`, `output_file`, `human_input`, `async_execution` and `markdown` work in YAML; put `output_pydantic`, `output_json`, function guardrails and `tools` in the Python method.

---

## 6. Task Dependencies and Context Flow

Tasks run in list order. A task without `context` receives the raw output of every earlier task.

```
research_task → analysis_task → report_task
     ↓               ↓              ↓
  (none)         output 1      output 1 + 2
```

You don't need `context=` for that - it's implicit. Use it to narrow or reshape the dependencies:

```python
# Diamond dependency pattern
task_a = Task(...)                            # Entry point
task_b = Task(..., context=[task_a])          # Depends on A
task_c = Task(..., context=[task_a])          # Also depends on A
task_d = Task(..., context=[task_b, task_c])  # Depends on both B and C
```

### Conditional Tasks

```python
from pydantic import BaseModel

from crewai import Task, TaskOutput
from crewai.tasks.conditional_task import ConditionalTask   # not crewai.task

class Items(BaseModel):
    items: list[str]

gather = Task(description="List data sources for {topic}...", expected_output="A list of sources.",
              agent=researcher, output_pydantic=Items)   # the condition below reads .pydantic

def needs_more_data(output: TaskOutput) -> bool:
    return len(output.pydantic.items) < 10

extra_research = ConditionalTask(description="Fetch additional data sources...", expected_output="...",
                                 agent=researcher,
                                 condition=needs_more_data)  # runs only if the previous output has < 10 items
```

The condition receives the `TaskOutput` of the task immediately before it. A skipped conditional task still appears in `result.tasks_output`, with `raw == ""`. A `ConditionalTask` cannot be the first task, cannot be async, and a crew cannot consist only of conditional tasks.

---

## 7. Task Tools

Tasks can have their own tools that replace the agent's default tools for that specific task:

```python
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

Task(description="Search for and scrape the top 5 articles about {topic}...", expected_output="...",
     agent=researcher, tools=[SerperDevTool(), ScrapeWebsiteTool()])  # task-specific tools
```

If `tools` is set on the task, the agent gets **only** those tools for that task - the lists are not merged. Leave it unset to use the agent's tools.

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
    Research {topic} trends for {current_year}, targeting {target_audience}.
  expected_output: >
    A report on {topic} suitable for {target_audience}.
```

Variables are replaced at kickoff: `crew.kickoff(inputs={"topic": "AI Agents", "current_year": "2026", "target_audience": "developers"})`.

**Common mistakes:**
- Missing variable in `inputs` → kickoff raises `ValueError: Missing required template variable ... 'audience' not found in inputs dictionary`
- Using `{{ }}` Jinja2 syntax → crewAI uses single braces `{ }`; `{{topic}}` renders as `{AI Agents}`
- Unused variables in `inputs` → silently ignored (no error)

---

## 9. Common Task Design Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| Vague description ("Research the topic") | Agent produces shallow, unfocused output | Add specific steps, constraints, and context |
| Vague expected_output ("A report") | Agent guesses at format and structure | Specify format, sections, length, quality markers |
| Multiple objectives in one task | Agent does all of them poorly | Split into focused single-purpose tasks |
| Modeling each chat turn as a Crew task | Tasks are batch/workflow units, not the conversational session loop | Use a conversational Flow and call `handle_turn()` per user message |
| Downstream task sees too much or the wrong prior output | Every earlier output is passed by default | Use `context=[prior_task]` (or `context=[]`) to choose |
| `expected_output` references a Pydantic class | Agent sees a class name string, not field names | Keep `expected_output` as a human-readable string; use `output_pydantic` for the model |
| `output_pydantic` set in `tasks.yaml` | `KeyError`, or the model is dropped and `.pydantic` is `None` | Set `output_pydantic=Model` in the `@task` method |
| Two async tasks on the same agent | `RuntimeError: Executor is already running` | One agent per concurrently running async task |
| `human_input=True` in CI or a server | `EOFError` after wasted retries | Pipe answers into stdin, or use Flow `@human_feedback` |
| Missing tools for data tasks | Agent fabricates data instead of fetching it | Add tools to the task or agent |
| No guardrails on critical output | Bad output flows downstream unchecked | Add function or LLM guardrails |
| Overly strict expected_output or guardrail | Agent retries until `Task failed guardrail validation` | Be specific but achievable; lower `guardrail_max_retries` to fail faster |
| Description duplicates backstory | Wasted tokens and confused agent | Description = what to do; backstory = who you are |

---

## 10. Task Design Checklist

Before running a task, verify:

- [ ] **Description** includes what, how, context, and constraints
- [ ] **Expected output** specifies format, structure, and quality markers
- [ ] **Single purpose** - one clear objective per task
- [ ] **Agent assigned** (required in sequential crews and for string guardrails)
- [ ] **Dependencies** set via `context` where the default (all prior outputs) is wrong
- [ ] **Tools** provided for any task requiring external data
- [ ] **Structured output** set in Python, and `.pydantic` asserted non-None
- [ ] **Guardrails** set for critical outputs, returning `(bool, value)`
- [ ] **Async tasks** each on their own agent, followed by a synchronous task
- [ ] **Variables** in YAML match the `inputs` dict keys
- [ ] **Expected output is achievable** - test with a simple run before adding complexity

---

## References

For deeper dives into specific topics, see:

- [Structured Output](references/structured-output.md) - `output_pydantic`, `output_json`, `response_model` and `response_format` across LLM, Agent, Task, and Crew levels

For related skills:

- **check-crewai-api** - current imports, parameter names, structured output and guardrail forms for crewai 1.15.x
- **getting-started** - project scaffolding, choosing the right abstraction, Flow architecture
- **design-agent** - agent Role-Goal-Backstory framework, parameter tuning, tool assignment, memory & knowledge configuration
- **build-flow** - Flow state, routers and `@human_feedback`
- **ask-docs** - query the live CrewAI docs for questions not covered by these skills
