---
name: design-agent
description: "CrewAI agent design and configuration. Use when creating, configuring, or debugging crewAI agents — choosing role/goal/backstory, selecting LLMs, assigning tools, tuning max_iter/max_rpm/max_execution_time, enabling planning/code execution/delegation, setting up knowledge sources, using guardrails, or configuring agents in YAML vs code."
---

# CrewAI Agent Design Guide

How to design effective agents with the right role, goal, backstory, tools, and configuration.

---

## The 80/20 Rule

**Spend 80% of your effort on task design, 20% on agent design.** A well-designed task elevates even a simple agent. But even the best agent cannot rescue a vague, poorly scoped task. Get the task right first (see the `design-task` skill), then refine the agent.

---

## 1. The Role-Goal-Backstory Framework

Every agent needs three things: **who** it is, **what** it wants, and **why** it's qualified.

### Role — Who the Agent Is

The role defines the agent's area of expertise. **Be specific, not generic.**

| Bad | Good |
|---|---|
| `Researcher` | `Senior Data Researcher specializing in {topic}` |
| `Writer` | `Technical Blog Writer for developer audiences` |
| `Analyst` | `Financial Risk Analyst with regulatory compliance expertise` |

The role directly shapes how the LLM reasons. A "Senior Data Researcher" will produce different output than a "Research Assistant" even with the same task.

### Goal — What the Agent Wants

The goal is the agent's individual objective. It should be **outcome-focused with quality standards**.

| Bad | Good |
|---|---|
| `Do research` | `Uncover cutting-edge developments in {topic} and identify the top 5 trends with supporting evidence` |
| `Write content` | `Produce publication-ready technical articles that explain complex topics clearly for non-technical readers` |
| `Analyze data` | `Deliver actionable risk assessments with confidence levels and recommended mitigations` |

### Backstory — Why the Agent Is Qualified

The backstory establishes expertise, experience, values, and working style. It's the agent's "personality prompt."

```yaml
backstory: >
  You're a seasoned researcher with 15 years of experience in AI/ML.
  You're known for your ability to find obscure but relevant papers
  and synthesize complex findings into clear, actionable insights.
  You always cite your sources and flag uncertainty explicitly.
```

**What to include in a backstory:**
- Years/depth of experience
- Specific domain knowledge
- Working style and values (e.g., "always cites sources", "prefers concise output")
- Quality standards the agent holds itself to

**What NOT to include:**
- Implementation details (tools, models, config)
- Task-specific instructions (those go in the task description)
- Arbitrary personality traits that don't affect output quality

---

## 2. Agent Configuration Reference

### Essential Parameters

```python
Agent(
    role="...",              # Required: agent's expertise area
    goal="...",              # Required: what the agent aims to achieve
    backstory="...",         # Required: context and personality
    llm="openai/gpt-4o",    # Optional: defaults to OPENAI_MODEL_NAME env var or "gpt-4"
    tools=[...],             # Optional: list of tool instances
)
```

### Execution Control

```python
Agent(
    ...,
    max_iter=25,             # Max reasoning iterations per task (default: 25)
    max_execution_time=300,  # Timeout in seconds (default: None — no limit)
    max_rpm=10,              # Rate limit: max API calls per minute (default: None)
    max_retry_limit=2,       # Retries on error (default: 2)
    verbose=True,            # Show detailed execution logs (default: False)
)
```

**Tuning `max_iter`:**
- Default 25 is generous — most tasks finish in 3-8 iterations
- Lower to 10-15 to fail faster when tasks are well-defined
- If agent consistently hits max_iter, the task is too vague (fix the task, not the limit)

### Tool Configuration

```python
from crewai_tools import SerperDevTool, ScrapeWebsiteTool, FileReadTool

Agent(
    ...,
    tools=[SerperDevTool(), ScrapeWebsiteTool()],  # Agent-level tools
)
```

**Key rules:**
- An agent with **no tools** will hallucinate data when asked to search, fetch, or read files — always provide tools for tasks that require external data
- Prefer **fewer, focused tools** over many tools — too many tools confuses the agent
- Tools can also be assigned at the **task level** for task-specific access (see `design-task` skill)
- Agent-level tools are available for all tasks the agent performs; task-level tools override for that specific task

### LLM Selection

```python
Agent(
    ...,
    llm="openai/gpt-4o",              # Main reasoning model
    function_calling_llm="openai/gpt-4o-mini",  # Cheaper model for tool calls only
)
```

Use `function_calling_llm` to save costs: the main `llm` handles reasoning while a cheaper model handles tool-calling mechanics.

### Collaboration

```python
Agent(
    ...,
    allow_delegation=False,  # Default: False — agent works alone
)
```

Set `allow_delegation=True` only when:
- The agent is part of a crew with other specialized agents
- The task genuinely benefits from the agent handing off subtasks
- You're using hierarchical process where the manager delegates

**Warning:** Delegation without clear task boundaries leads to infinite loops or wasted iterations.

### Planning (Reasoning Before Acting)

```python
from crewai.agents.agent_builder.base_agent import PlanningConfig

Agent(
    ...,
    planning=True,                    # Enable plan-then-execute (default: False)
    planning_config=PlanningConfig(
        max_attempts=3,               # Max planning iterations
    ),
)
```

Use planning for complex tasks where the agent benefits from thinking through its approach before taking action. Skip it for simple, well-defined tasks.

### Code Execution

```python
Agent(
    ...,
    allow_code_execution=True,        # Enable code execution (default: False)
    code_execution_mode="safe",       # "safe" (Docker) or "unsafe" (direct) — default: "safe"
)
```

- `"safe"` requires Docker installed and running — executes in a container
- `"unsafe"` runs code directly on the host — only use in controlled environments

### Context Window Management

```python
Agent(
    ...,
    respect_context_window=True,      # Auto-summarize to stay within limits (default: True)
)
```

When `True`, the agent automatically summarizes prior context if it approaches the LLM's token limit. When `False`, execution stops with an error on overflow.

### Date Injection

```python
Agent(
    ...,
    inject_date=True,                 # Add current date to task context (default: False)
    date_format="%Y-%m-%d",           # Date format (default: "%Y-%m-%d")
)
```

Enable for time-sensitive tasks (research, news analysis, scheduling).

### Agent Guardrails

```python
def validate_no_pii(result) -> tuple[bool, Any]:
    """Reject output containing PII."""
    if contains_pii(result.raw):
        return (False, "Output contains PII. Remove all personal information and try again.")
    return (True, result)

Agent(
    ...,
    guardrail=validate_no_pii,
    guardrail_max_retries=3,          # default: 3
)
```

Agent guardrails validate every output the agent produces. The agent retries on failure up to `guardrail_max_retries`.

### Knowledge Sources

```python
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

Agent(
    ...,
    knowledge_sources=[
        TextFileKnowledgeSource(file_paths=["company_handbook.txt"]),
    ],
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
)
```

Knowledge sources give agents access to domain-specific data via RAG. Use when agents need to reference large documents, policies, or datasets.

---

## 3. YAML Configuration (Recommended)

Define agents in `agents.yaml` for clean separation of config and code:

```yaml
researcher:
  role: >
    {topic} Senior Data Researcher
  goal: >
    Uncover cutting-edge developments in {topic}
    with supporting evidence and source citations
  backstory: >
    You're a seasoned researcher with 15 years of experience.
    Known for finding obscure but relevant sources and
    synthesizing complex findings into clear insights.
    You always cite your sources and flag uncertainty.
  # Optional overrides (uncomment as needed):
  # llm: openai/gpt-4o
  # max_iter: 15
  # max_rpm: 10
  # allow_delegation: false
  # verbose: true
```

Then wire in `crew.py`:

```python
@CrewBase
class MyCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            tools=[SerperDevTool()],
        )
```

**Critical:** The method name (`def researcher`) must match the YAML key (`researcher:`). Mismatch causes `KeyError`.

---

## 4. Agent.kickoff() — Direct Agent Execution

Use `Agent.kickoff()` when you need one agent with tools and reasoning, without crew overhead. This is the most common pattern in Flows.

### Basic Usage

```python
from crewai import Agent
from crewai_tools import SerperDevTool

researcher = Agent(
    role="Senior Research Analyst",
    goal="Find comprehensive, factual information with source citations",
    backstory="Expert researcher known for thorough, evidence-based analysis.",
    tools=[SerperDevTool()],
    llm="openai/gpt-4o",
)

# Pass a string prompt — the agent reasons, uses tools, and returns a result
result = researcher.kickoff("What are the latest developments in quantum computing?")
print(result.raw)             # str — the agent's full response
print(result.usage_metrics)   # token usage stats
```

### With Structured Output

```python
from pydantic import BaseModel

class ResearchFindings(BaseModel):
    key_trends: list[str]
    sources: list[str]
    confidence: float

result = researcher.kickoff(
    "Research the latest AI agent frameworks",
    response_format=ResearchFindings,
)

# Access via .pydantic (NOT directly — Agent.kickoff wraps the result)
print(result.pydantic.key_trends)    # list[str]
print(result.pydantic.confidence)    # float
print(result.raw)                    # raw string version
```

> **Note:** `Agent.kickoff()` returns `LiteAgentOutput` — access structured output via `result.pydantic`. This differs from `LLM.call()` which returns the Pydantic object directly.

### With File Inputs

```python
result = researcher.kickoff(
    "Analyze this document and summarize the key findings",
    input_files={"document": FileInput(path="report.pdf")},
)
```

### Async Variant

```python
result = await researcher.kickoff_async(
    "Research quantum computing breakthroughs",
    response_format=ResearchFindings,
)
```

### Agent.kickoff() in Flows (Recommended Pattern)

The most powerful pattern is orchestrating multiple `Agent.kickoff()` calls inside a Flow. The Flow handles state and sequencing; each agent handles its specific step:

```python
from crewai import Agent
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from pydantic import BaseModel

class ResearchState(BaseModel):
    topic: str = ""
    research: str = ""
    analysis: str = ""
    report: str = ""

class ResearchFlow(Flow[ResearchState]):

    @start()
    def gather_data(self):
        researcher = Agent(
            role="Senior Researcher",
            goal="Find comprehensive data with sources",
            backstory="Expert at finding and validating information.",
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
        )
        result = researcher.kickoff(f"Research: {self.state.topic}")
        self.state.research = result.raw

    @listen(gather_data)
    def analyze(self):
        analyst = Agent(
            role="Data Analyst",
            goal="Extract actionable insights from raw research",
            backstory="Skilled at pattern recognition and synthesis.",
        )
        result = analyst.kickoff(
            f"Analyze this research and extract key insights:\n\n{self.state.research}"
        )
        self.state.analysis = result.raw

    @listen(analyze)
    def write_report(self):
        writer = Agent(
            role="Report Writer",
            goal="Create clear, well-structured reports",
            backstory="Technical writer who makes complex topics accessible.",
        )
        result = writer.kickoff(
            f"Write a comprehensive report from this analysis:\n\n{self.state.analysis}"
        )
        self.state.report = result.raw

flow = ResearchFlow()
flow.kickoff(inputs={"topic": "AI agents"})
print(flow.state.report)
```

**When to use Agent.kickoff() vs Crew.kickoff():**
- Use `Agent.kickoff()` when each step is a distinct agent and the Flow controls sequencing
- Use `Crew.kickoff()` when multiple agents need to collaborate on related tasks within a single step

---

## 5. Specialist vs Generalist Agents

**Always prefer specialists.** An agent that does one thing well outperforms one that does many things acceptably.

### When to Use a Specialist

- Task requires deep domain knowledge
- Output quality matters more than speed
- The task is complex enough to benefit from focused expertise

### When a Generalist Is Acceptable

- Simple tasks with clear instructions
- Prototyping where you'll specialize later
- Tasks that truly span multiple domains equally

### Specialist Design Pattern

Instead of one "Content Writer" agent, create:
- `technical_writer` — deep technical accuracy, code examples
- `copywriter` — persuasive, audience-focused marketing copy
- `editor` — grammar, consistency, style guide enforcement

Each specialist has a narrow role, specific goal, and backstory that reinforces their expertise.

---

## 6. Agent Interaction Patterns

### Sequential (Default)

Agents work one after another. Each agent receives prior agents' outputs as context.

```
Researcher → Writer → Editor
```

Best for: linear pipelines where each step builds on the last.

### Hierarchical

A manager agent delegates and validates. Task assignment is dynamic.

```python
Crew(
    agents=[researcher, writer, editor],
    tasks=[research_task, writing_task, editing_task],
    process=Process.hierarchical,
    manager_llm="openai/gpt-4o",
)
```

Best for: complex workflows where task assignment depends on intermediate results.

### Agent-to-Agent Delegation

When `allow_delegation=True`, an agent can ask another crew agent for help:

```python
lead_researcher = Agent(
    role="Lead Researcher",
    goal="Coordinate research efforts",
    backstory="...",
    allow_delegation=True,  # Can delegate to other agents in the crew
)
```

The agent will automatically discover other crew members and delegate subtasks as needed.

---

## 7. Common Agent Design Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| Generic role like "Assistant" | Agent produces unfocused, shallow output | Use specific expertise: "Senior Financial Analyst" |
| No tools for data-gathering tasks | Agent hallucinates data instead of searching | Always add tools when the task requires external info |
| Too many tools (10+) | Agent gets confused choosing between tools | Limit to 3-5 relevant tools per agent |
| Backstory full of task instructions | Agent mixes personality with task execution | Keep backstory about WHO the agent is; task details go in the task |
| `allow_delegation=True` by default | Agents waste iterations delegating trivially | Only enable when delegation genuinely helps |
| max_iter too high for simple tasks | Agent loops unnecessarily on vague tasks | Lower max_iter; fix the task description instead |
| No guardrail on critical output | Bad output passes through unchecked | Add guardrails for outputs that feed into production systems |
| Using expensive LLM for tool calls | Unnecessary cost for mechanical operations | Set `function_calling_llm` to a cheaper model |

---

## 8. Agent Design Checklist

Before deploying an agent, verify:

- [ ] **Role** is specific and domain-focused (not "Assistant" or "Helper")
- [ ] **Goal** includes desired outcome AND quality standards
- [ ] **Backstory** establishes expertise and working style
- [ ] **Tools** are assigned for any task requiring external data
- [ ] **No excess tools** — 3-5 per agent maximum
- [ ] **max_iter** is tuned for expected task complexity (10-15 for simple, 20-25 for complex)
- [ ] **max_execution_time** is set for production agents to prevent hangs
- [ ] **Guardrails** are configured for critical outputs
- [ ] **LLM** is appropriate for task complexity (don't use GPT-4 for classification)
- [ ] **Delegation** is disabled unless genuinely needed

---

## References

For deeper dives into specific topics, see:

- [Custom Tools](references/custom-tools.md) — building your own tools with `@tool` decorator and `BaseTool` subclass
- [Memory & Knowledge](references/memory-and-knowledge.md) — memory configuration, knowledge sources, embedder setup, scoping

For related skills:

- **getting-started** — project scaffolding, choosing the right abstraction, Flow architecture
- **design-task** — task description/expected_output best practices, guardrails, structured output, dependencies
- **ask-docs** — query the live CrewAI documentation MCP server for questions not covered by these skills
