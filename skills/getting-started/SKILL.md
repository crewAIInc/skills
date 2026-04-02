---
name: getting-started
description: "CrewAI architecture decisions and project scaffolding. Use when starting a new crewAI project, choosing between LLM.call() vs Agent.kickoff() vs Crew.kickoff() vs Flow, scaffolding with 'crewai create flow', setting up YAML config (agents.yaml, tasks.yaml), wiring @CrewBase crew.py, writing Flow main.py with @start/@listen, or using {variable} interpolation."
---

# CrewAI Getting Started & Architecture

How to choose the right abstraction, scaffold a project, and wire everything together.

---

## MANDATORY WORKFLOW — Read This First

**NEVER manually create crewAI project files.** Always scaffold with the CLI:

```bash
crewai create flow <project_name>
```

This is **not optional**. Even if you only need one crew, even if you know the file structure by heart — run the CLI first, then modify the generated files. Do NOT write `main.py`, `crew.py`, `agents.yaml`, `tasks.yaml`, or `pyproject.toml` by hand from scratch.

> **Why:** The CLI sets up correct imports, directory structure, pyproject.toml config, and boilerplate that is easy to get subtly wrong when done manually. The reference material below teaches you how the pieces work so you can *modify* scaffolded code, not so you can *replace* the scaffolding step.

**Workflow:**
1. Run `crewai create flow <name>` (use **underscores**, not hyphens)
2. Edit the generated YAML and Python files to match your use case
3. Run `crewai install` then `crewai run`

---

## 1. Choosing the Right Abstraction

crewAI has four levels of abstraction. Pick the simplest one that fits your need:

| Level | When to Use | Overhead | Example |
|---|---|---|---|
| `LLM.call()` | Single prompt, no tools, structured extraction | Lowest | Parse an email into fields |
| `Agent.kickoff()` | One agent with tools and reasoning, no multi-agent coordination | Low | Research a topic with web search |
| `Crew.kickoff()` | Multiple agents collaborating on related tasks | Medium | Research + write + review pipeline |
| `Flow` wrapping crews/agents/LLM calls | Production app with state, routing, conditionals, error handling | Full | Multi-step workflow with branching logic |

### Decision Flowchart

```
Do you need tools or multi-step reasoning?
├── No  → LLM.call()
└── Yes
    └── Do you need multiple agents collaborating?
        ├── No  → Agent.kickoff()
        └── Yes
            └── Do you need state management, routing, or multiple crews?
                ├── No  → Crew (but still scaffold as a Flow for future-proofing)
                └── Yes → Flow + Crew(s)
```

**Rule of thumb:** For any production application, **always start with a Flow**. You can embed `LLM.call()`, `Agent.kickoff()`, or `Crew.kickoff()` inside Flow steps. This gives you state management, error handling, and room to grow.

---

## 2. LLM.call() — Direct LLM Invocation

Use for simple, single-turn tasks where you don't need tools or agent reasoning.

```python
from crewai import LLM
from pydantic import BaseModel

class EmailFields(BaseModel):
    sender: str
    subject: str
    urgency: str

llm = LLM(model="openai/gpt-4o")

# Without response_format — returns a string
raw = llm.call(messages=[{"role": "user", "content": "Summarize this text..."}])
print(raw)  # str

# With response_format — returns the Pydantic object directly
result = llm.call(
    messages=[{"role": "user", "content": f"Extract fields from this email: {email_text}"}],
    response_format=EmailFields
)
print(result.sender)   # str — access Pydantic fields directly
print(result.urgency)  # str
```

**When NOT to use:** If you need tools, multi-step reasoning, or retries — use an Agent instead.

---

## 3. Agent.kickoff() — Single Agent Execution

Use when you need one agent with tools and reasoning, but don't need multi-agent coordination.

```python
from crewai import Agent
from crewai_tools import SerperDevTool
from pydantic import BaseModel

class ResearchFindings(BaseModel):
    main_points: list[str]
    key_technologies: list[str]

researcher = Agent(
    role="AI Researcher",
    goal="Research the latest AI developments",
    backstory="Expert AI researcher with deep technical knowledge.",
    llm="openai/gpt-4o",       # Optional: defaults to OPENAI_MODEL_NAME env var or "gpt-4"
    tools=[SerperDevTool()],
)

# Unstructured output
result = researcher.kickoff("What are the latest LLM developments?")
print(result.raw)            # str
print(result.usage_metrics)  # token usage

# Structured output with response_format
result = researcher.kickoff(
    "Summarize latest AI developments",
    response_format=ResearchFindings,
)
print(result.pydantic.main_points)
```

> **Note:** `Agent.kickoff()` wraps results — access structured output via `result.pydantic`. This differs from `LLM.call()`, which returns the Pydantic object directly.

**When NOT to use:** If you need multiple agents passing context to each other — use a Crew.

---

## 4. CLI Scaffold Reference

As stated above: **NEVER skip `crewai create flow`.** This section documents what the CLI generates so you know what to modify — not so you can recreate it by hand.

```bash
crewai create flow my_project
```

> **Warning:** Always use **underscores** in project names, not hyphens. `crewai create flow my-project` creates a directory that is not a valid Python identifier, causing `ModuleNotFoundError` on import. Use `my_project` instead.

This generates:

```
my_project/
├── src/my_project/
│   ├── crews/
│   │   └── my_crew/
│   │       ├── config/
│   │       │   ├── agents.yaml    # Agent definitions (role, goal, backstory)
│   │       │   └── tasks.yaml     # Task definitions (description, expected_output)
│   │       └── my_crew.py         # Crew class with @CrewBase
│   ├── tools/
│   │   └── custom_tool.py
│   ├── main.py                    # Flow class with @start/@listen
│   └── ...
├── .env                           # API keys (OPENAI_API_KEY, etc.)
└── pyproject.toml
```

> **Do not** use `crewai create crew` unless you are certain you will never need routing, state, or multiple crews. Prefer `crewai create flow` as the default.

---

## 5. YAML Configuration (agents.yaml & tasks.yaml)

The scaffold uses YAML files for agent and task definitions. This separates configuration from code and supports `{variable}` interpolation.

### agents.yaml

```yaml
researcher:
  role: >
    {topic} Senior Data Researcher
  goal: >
    Uncover cutting-edge developments in {topic}
  backstory: >
    You're a seasoned researcher with a knack for uncovering
    the latest developments in {topic}.
  # Optional overrides:
  # llm: openai/gpt-4o
  # max_iter: 20
  # max_rpm: 10

reporting_analyst:
  role: >
    {topic} Reporting Analyst
  goal: >
    Create detailed reports based on {topic} research findings
  backstory: >
    You're a meticulous analyst known for turning complex data
    into clear, actionable reports.
```

### tasks.yaml

```yaml
research_task:
  description: >
    Conduct thorough research about {topic}.
    Identify key trends, breakthrough technologies,
    and potential industry impacts.
  expected_output: >
    A detailed report with analysis of the top 5
    developments in {topic}, with sources and implications.
  agent: researcher

reporting_task:
  description: >
    Review the research and create a comprehensive report about {topic}.
  expected_output: >
    A polished report formatted in markdown with sections
    for each key finding.
  agent: reporting_analyst
  output_file: output/report.md
```

**Key rules:**
- `{variable}` placeholders are replaced at runtime via `crew.kickoff(inputs={...})`
- `expected_output` is always a **string** (never a Pydantic class name)
- `agent` value must match an agent key in `agents.yaml`
- In `Process.sequential`, each task auto-receives all prior task outputs as context
- For non-sequential deps, use `context=[other_task]` to explicitly pass output

---

## 6. Wiring It Together — crew.py

The `@CrewBase` decorator auto-loads YAML config files and collects `@agent` and `@task` methods.

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

@CrewBase
class ResearchCrew:
    """Research and reporting crew."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            tools=[SerperDevTool()],
        )

    @agent
    def reporting_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["reporting_analyst"],
        )

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def reporting_task(self) -> Task:
        return Task(
            config=self.tasks_config["reporting_task"],
            context=[self.research_task()],  # Explicit dependency (optional in sequential)
            output_file="output/report.md",
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,  # auto-collected by @agent
            tasks=self.tasks,    # auto-collected by @task
            process=Process.sequential,
            verbose=True,
        )
```

**Important:** Method names must match YAML keys. `def researcher(self)` maps to the `researcher:` key in `agents.yaml`.

---

## 7. Flows — The Production Foundation

Flows are the recommended way to build production crewAI applications. They provide state management, conditional routing, human-in-the-loop, and persistence — wrapping crews, agents, and LLM calls into a coherent workflow.

### Basic Flow — main.py

```python
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel
from .crews.research_crew.research_crew import ResearchCrew

class ResearchState(BaseModel):
    topic: str = ""
    report: str = ""

class ResearchFlow(Flow[ResearchState]):

    @start()
    def begin(self):
        print(f"Starting research on: {self.state.topic}")

    @listen(begin)
    def run_research(self):
        result = ResearchCrew().crew().kickoff(
            inputs={"topic": self.state.topic}
        )
        self.state.report = result.raw

def kickoff():
    flow = ResearchFlow()
    flow.kickoff(inputs={"topic": "AI Agents"})

if __name__ == "__main__":
    kickoff()
```

**Key points:**
- `flow.kickoff(inputs={"topic": "AI Agents"})` populates `self.state.topic` (keys must match Pydantic field names). The YAML `{variable}` substitution happens later, when you call `crew.kickoff(inputs={"topic": self.state.topic})` inside a Flow step. The chain is: **flow inputs → state → crew inputs → YAML substitution**.
- Each `@listen` method runs after its dependency completes
- State persists across all Flow steps — use it to pass data between crews

### State Management — Structured vs Unstructured

**Structured (recommended for production):**
```python
from pydantic import BaseModel

class MyState(BaseModel):
    topic: str = ""
    research: str = ""
    draft: str = ""
    approved: bool = False

class MyFlow(Flow[MyState]):
    ...
```

**Unstructured (quick prototyping):**
```python
class MyFlow(Flow):  # No type parameter — state is a dict
    @start()
    def begin(self):
        self.state["topic"] = "AI"  # dict-style access
```

Use structured state for type safety, IDE autocompletion, and validation. Use unstructured only for throwaway prototypes.

### Using Agent.kickoff() Inside Flows (Common Pattern)

Many production Flows skip Crews entirely and orchestrate individual agents via `Agent.kickoff()`. This gives you fine-grained control — each Flow step calls a specific agent, passes state, and stores the result. The Flow handles orchestration; agents handle reasoning.

```python
from crewai import Agent, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from pydantic import BaseModel

class ResearchState(BaseModel):
    query: str = ""
    raw_research: str = ""
    analysis: str = ""
    report: str = ""

class DeepResearchFlow(Flow[ResearchState]):

    @start()
    def gather_research(self):
        """Agent with tools does the actual searching."""
        researcher = Agent(
            role="Senior Research Analyst",
            goal="Find comprehensive, factual information about the given topic",
            backstory="You're an expert researcher who always cites sources and flags uncertainty.",
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
            llm="openai/gpt-4o",
        )
        result = researcher.kickoff(
            f"Research this topic thoroughly: {self.state.query}"
        )
        self.state.raw_research = result.raw

    @listen(gather_research)
    def analyze_findings(self):
        """A different agent analyzes the raw research — no tools needed."""
        analyst = Agent(
            role="Data Analyst",
            goal="Extract key insights, patterns, and actionable recommendations",
            backstory="You turn raw data into clear, structured analysis.",
            llm="openai/gpt-4o",
        )
        result = analyst.kickoff(
            f"Analyze these research findings and extract key insights:\n\n{self.state.raw_research}"
        )
        self.state.analysis = result.raw

    @listen(analyze_findings)
    def write_report(self):
        """A writer agent produces the final deliverable."""
        writer = Agent(
            role="Technical Writer",
            goal="Produce clear, actionable reports for non-technical readers",
            backstory="You specialize in making complex information accessible.",
            llm="openai/gpt-4o",
        )
        result = writer.kickoff(
            f"Write a comprehensive report based on this analysis:\n\n{self.state.analysis}"
        )
        self.state.report = result.raw
```

**Why this pattern works well:**
- Each agent is purpose-built for its step — narrow role, specific tools
- The Flow manages state and sequencing — no crew overhead
- Easy to add routing, human review, or retry logic between steps
- You can mix `Agent.kickoff()`, `LLM.call()`, and `Crew.kickoff()` freely

**When to use Agent.kickoff() vs Crew.kickoff() in a Flow:**

| Use `Agent.kickoff()` when | Use `Crew.kickoff()` when |
|---|---|
| Each step is a distinct agent with different tools | Multiple agents need to collaborate on ONE task |
| You want the Flow to control sequencing | Agents need to pass context to each other within a step |
| Steps are independent and don't need inter-agent delegation | You need hierarchical process with a manager |
| You want maximum control over what data flows between steps | The sub-workflow is self-contained and reusable |

### Agent.kickoff() with Structured Output in Flows

Combine `response_format` with state for typed data flow between agents:

```python
class Insights(BaseModel):
    key_points: list[str]
    recommendations: list[str]
    confidence: float

class AnalysisFlow(Flow[AnalysisState]):

    @start()
    def research(self):
        researcher = Agent(role="Researcher", goal="...", backstory="...", tools=[SerperDevTool()])
        result = researcher.kickoff(
            f"Research {self.state.topic}",
            response_format=Insights,
        )
        # result.pydantic gives you the typed Insights object
        self.state.key_points = result.pydantic.key_points
        self.state.recommendations = result.pydantic.recommendations
```

### Mixing Abstractions in a Flow

A Flow can combine all crewAI abstractions in a single workflow:

```python
class ProductFlow(Flow[ProductState]):

    @start()
    def classify_request(self):
        # LLM.call() for simple classification
        llm = LLM(model="openai/gpt-4o")
        self.state.category = llm.call(
            messages=[{"role": "user", "content": f"Classify: {self.state.request}"}],
            response_format=Category
        ).category

    @router(classify_request)
    def route_by_category(self):
        if self.state.category == "simple":
            return "quick_answer"
        return "deep_research"

    @listen("quick_answer")
    def handle_simple(self):
        # Agent.kickoff() for single-agent work
        agent = Agent(role="Helper", goal="Answer quickly", backstory="...")
        result = agent.kickoff(self.state.request)
        self.state.answer = result.raw

    @listen("deep_research")
    def handle_complex(self):
        # Crew.kickoff() for multi-agent collaboration
        result = ResearchCrew().crew().kickoff(
            inputs={"topic": self.state.request}
        )
        self.state.answer = result.raw
```

### Flow Routing with `@router`

Use `@router` for conditional branching — return a string label, and `@listen("label")` binds to branches:

```python
from crewai.flow.flow import Flow, listen, router, start, or_

class QualityFlow(Flow[QAState]):

    @start()
    def generate_content(self):
        result = WriterCrew().crew().kickoff(inputs={"topic": self.state.topic})
        self.state.draft = result.raw

    @router(generate_content)
    def check_quality(self):
        llm = LLM(model="openai/gpt-4o")
        score = llm.call(
            messages=[{"role": "user", "content": f"Rate 1-10: {self.state.draft}"}],
            response_format=QualityScore
        )
        if score.rating >= 7:
            return "approved"
        return "needs_revision"

    @listen("approved")
    def publish(self):
        self.state.published = True

    @listen("needs_revision")
    def revise(self):
        result = EditorCrew().crew().kickoff(
            inputs={"draft": self.state.draft}
        )
        self.state.draft = result.raw
```

### Converging Branches with `or_()` and `and_()`

```python
from crewai.flow.flow import Flow, listen, start, or_, and_

class ParallelFlow(Flow[MyState]):

    @start()
    def fetch_data_a(self):
        ...

    @start()
    def fetch_data_b(self):
        ...

    # Runs when BOTH fetches complete
    @listen(and_(fetch_data_a, fetch_data_b))
    def merge_results(self):
        ...

    # Runs when EITHER source provides data
    @listen(or_(fetch_data_a, fetch_data_b))
    def process_first_available(self):
        ...
```

### Flow Persistence with `@persist`

For long-running workflows that need to survive restarts:

```python
from crewai.flow.flow import Flow, start, listen, persist
from crewai.flow.persistence import SQLiteFlowPersistence

@persist(SQLiteFlowPersistence())  # Class-level: persists all methods
class LongRunningFlow(Flow[MyState]):

    @start()
    def step_one(self):
        self.state.data = "processed"

    @listen(step_one)
    def step_two(self):
        # If the process crashes here, restarting with the same
        # state ID will resume from after step_one
        ...
```

### Human-in-the-Loop with `@human_feedback`

```python
from crewai.flow.flow import Flow, start, listen, router
from crewai.flow.human_feedback import human_feedback

class ApprovalFlow(Flow[ReviewState]):

    @start()
    def generate_draft(self):
        result = WriterCrew().crew().kickoff(inputs={"topic": self.state.topic})
        self.state.draft = result.raw

    @human_feedback(
        message="Review the draft and provide feedback",
        emit=["approved", "needs_revision"],
        llm="openai/gpt-4o",
        default_outcome="approved"
    )
    @listen(generate_draft)
    def review_step(self):
        return self.state.draft

    @listen("approved")
    def publish(self):
        ...

    @listen("needs_revision")
    def revise(self):
        feedback = self.last_human_feedback
        # Use feedback.feedback_text for revision
        ...
```

### Flow Visualization

```python
flow = MyFlow()
flow.plot()             # Display in notebook
flow.plot("my_flow")    # Save as my_flow.png
```

---

## 8. Variable Interpolation with `inputs`

The `{variable}` pattern is how you make crews reusable.

```python
# Variables flow through: kickoff → YAML templates → agent/task prompts
crew.kickoff(inputs={
    "topic": "AI Agents",
    "current_year": "2025",
    "target_audience": "developers",
})
```

In YAML, `{topic}` and `{current_year}` get replaced:

```yaml
research_task:
  description: >
    Research {topic} trends for {current_year},
    targeting {target_audience}.
```

**Common mistakes:**
- Forgetting to pass a variable that's referenced in YAML → results in literal `{variable}` in the prompt
- Using Jinja2 syntax `{{ }}` instead of single-brace `{ }` → crewAI uses single braces
- Passing variables that don't match any YAML placeholder → silently ignored

---

## 9. Running Your Project

```bash
# Install dependencies
crewai install

# Run the flow
crewai run
```

Or run directly:

```bash
cd my_project
uv run src/my_project/main.py
```

---

## 10. Quick Diagnostic Checklist

| Symptom | Likely Cause | Fix |
|---|---|---|
| `{topic}` appears literally in agent output | Missing `inputs=` in `kickoff()` | Pass `crew.kickoff(inputs={"topic": "..."})` |
| `KeyError` on `self.agents_config['name']` | Method name doesn't match YAML key | Ensure `@agent def researcher` matches `researcher:` in YAML |
| `ModuleNotFoundError` on import | Wrong path or hyphens in project name | Use underscores; check `from .crews.crew_name.crew_name import CrewClass` |
| Crew runs but Flow state is empty | Not writing results back to `self.state` | Assign crew output to `self.state.field` in the `@listen` method |
| `Process.SEQUENTIAL` raises `AttributeError` | Uppercase enum | Use lowercase: `Process.sequential` |
| Agent ignores tools | Tools assigned to agent but task needs them | Move tools to task level or verify agent has the right tools |
| Agent fabricates search results | No tools assigned — agent can't actually search | Add `tools=[SerperDevTool()]` or equivalent; an agent with no tools will hallucinate data |
| `@listen` never fires | Listener string doesn't match router return value, or passed a string instead of method reference | `@router` must return the exact string `@listen("label")` expects; for method chaining use `@listen(method_ref)` not `@listen("method_name")` |
| Flow step runs twice unexpectedly | Multiple `@start()` methods or `or_` listener | Use `and_()` if you need all upstream steps to complete first |
| `AuthenticationError` or `API key not found` | Missing env var | Set `OPENAI_API_KEY` (and `SERPER_API_KEY` for search tools) in `.env` |
| Agent retries endlessly on structured output | Pydantic model too complex for the LLM | Simplify the model, reduce nesting, or use a more capable `llm` |
| Agent loops to `max_iter` without finishing | Task description too vague or conflicting with `expected_output` | Make `expected_output` specific and achievable; lower `max_iter` to fail faster |
| Flow state not updating across steps | Using unstructured state without proper key access | Switch to structured Pydantic state or ensure dict keys are consistent |
| `@router` return value ignored | Method not decorated with `@router` | Use `@router(condition)` not `@listen(condition)` for branching methods |

---

## References

For deeper dives into specific topics, see:

- [Flow Routing, Persistence, Streaming & Human Feedback](references/flow-routing.md) — complete `@router`, `or_()`, `and_()`, `@persist`, streaming, and `@human_feedback` patterns
- [MCP Servers](references/mcp-servers.md) — prefer official MCP servers over native tools; setup, DSL integration, and known official servers
- [Tools Catalog](references/tools-catalog.md) — all 80+ built-in tools with imports, env vars, and common combos (use as fallback when no MCP server exists)

For related skills:

- **design-agent** — agent Role-Goal-Backstory framework, parameter tuning, tool assignment, memory & knowledge configuration
- **design-task** — task description/expected_output best practices, guardrails, structured output, dependencies
- **ask-docs** — query the live CrewAI documentation MCP server for questions not covered by these skills
