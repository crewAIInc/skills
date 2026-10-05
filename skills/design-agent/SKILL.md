---
name: design-agent
description: "CrewAI agent design and configuration. Use when creating, configuring, or debugging crewAI agents — choosing role/goal/backstory, selecting LLMs, assigning tools, tuning max_iter/max_rpm/max_execution_time, enabling planning/delegation, setting up knowledge sources, using guardrails, or configuring agents in YAML vs code."
---

# CrewAI Agent Design Guide

How to design effective agents with the right role, goal, backstory, tools, and configuration.

Verified against crewai 1.15.23 on 2026-10-01.
Live-tested with real LLMs on 2026-10-01.

Exact API forms (imports, defaults, provider extras, structured output) are in the **check-crewai-api** skill, and tools and MCP are in **connect-tools-and-mcp**. Where this skill and those disagree, follow them.

---

## The 80/20 Rule

**Spend 80% of your effort on task design, 20% on agent design.** A well-designed task elevates even a simple agent. But even the best agent cannot rescue a vague, poorly scoped task. Get the task right first (see the `design-task` skill), then refine the agent.

---

## 0. How Many Agents Do You Actually Need?

**Default to ONE agent.** Add more only when the task genuinely splits into work that requires:

- **Different tools or permissions** - e.g. one agent has Slack write access, another reads docs only.
- **Different personas the LLM must clearly switch between** - a writer's voice is not a researcher's voice.
- **Different LLMs** - a cheap model for mechanical steps, a stronger one for synthesis.
- **Different guardrails or output schemas** - separate agents make the contract per stage explicit.

**DO NOT add an agent just because the workflow has multiple steps.** A single agent can call multiple tools in sequence within one kickoff (search → scrape → summarize is one agent's loop), produce structured multi-section output in one response, and iterate via its own tool-use loop.

**Cost calculus:** every extra agent = at least one more LLM kickoff plus a context handoff. Splitting linear, single-persona work into multiple agents multiplies token cost and adds fragility for marginal quality wins.

### Anti-patterns

❌ Three agents for what is one researcher's job:
```python
source_finder = Agent(role="Finds URLs via Firecrawl search", tools=[firecrawl_search])
scraper       = Agent(role="Scrapes URLs via Firecrawl scrape", tools=[firecrawl_scrape])
writer        = Agent(role="Writes the report")  # plus goal, backstory, llm
```

✅ One researcher does the gathering loop; one writer synthesizes - two agents because the personas and LLMs genuinely differ:
```python
researcher = Agent(role="Web Researcher", tools=[firecrawl_search, firecrawl_scrape], llm="anthropic/claude-haiku-4-5")
writer     = Agent(role="Technical Report Writer",                                    llm="anthropic/claude-sonnet-4-6")
```

❌ A `Summarizer` agent plus a `Slack Sender` agent (`apps=["slack"]`) to summarize a string and DM it.
✅ One `Slack Reporter` agent with `apps=["slack"]` and a task: "Write a 2-3 sentence executive summary at the top, then DM {recipient_email} the summary followed by the full body."

> **Heuristic:** if two "agents" share the same persona, the same tool surface, and the same LLM, they are one agent with a longer task description.

### Once you've decided "one agent is enough"

Use `Agent.kickoff()` directly inside a Flow method - no `Crew`, no `Task` ceremony. The Flow owns sequencing and state; each step is a single agent kickoff (Flow mechanics: **build-flow** skill; docs: <https://docs.crewai.com/en/concepts/agents#direct-agent-interaction-with-kickoff>).

```python
@listen(previous_step)
def my_step(self):
    agent = Agent(role="…", goal="…", backstory="…", tools=[...], llm="anthropic/claude-haiku-4-5")
    result = agent.kickoff(
        f"Use this prior step's output: {self.state.prior_field}",
        response_format=MyPydanticModel,  # optional
    )
    self.state.my_field = result.pydantic  # or result.raw
```

Reach for `Crew.kickoff()` *only* when a step genuinely benefits from multi-agent collaboration (delegation, hierarchical management, parallel specialists feeding one synthesis), or when the agent needs something that only works inside a crew task: **knowledge sources** and **`max_execution_time`** (Section 2).

---

## 1. The Role-Goal-Backstory Framework

Every agent needs three things: **who** it is, **what** it wants, and **why** it's qualified. `{placeholders}` in all three are filled from `crew.kickoff(inputs={...})`.

### Role - Who the Agent Is

The role defines the agent's area of expertise. **Be specific, not generic.**

| Bad | Good |
|---|---|
| `Researcher` | `Senior Data Researcher specializing in {topic}` |
| `Writer` | `Technical Blog Writer for developer audiences` |
| `Analyst` | `Financial Risk Analyst with regulatory compliance expertise` |

The role directly shapes how the LLM reasons. A "Senior Data Researcher" will produce different output than a "Research Assistant" even with the same task.

### Goal - What the Agent Wants

The goal is the agent's individual objective. It should be **outcome-focused with quality standards**.

| Bad | Good |
|---|---|
| `Do research` | `Uncover cutting-edge developments in {topic} and identify the top 5 trends with supporting evidence` |
| `Write content` | `Produce publication-ready technical articles that explain complex topics clearly for non-technical readers` |
| `Analyze data` | `Deliver actionable risk assessments with confidence levels and recommended mitigations` |

### Backstory - Why the Agent Is Qualified

The backstory establishes expertise, experience, values, and working style. It's the agent's "personality prompt."

```yaml
backstory: >
  You're a seasoned researcher with 15 years of experience in AI/ML.
  You're known for your ability to find obscure but relevant papers
  and synthesize complex findings into clear, actionable insights.
  You always cite your sources and flag uncertainty explicitly.
```

**Include:** years/depth of experience, specific domain knowledge, working style and values ("always cites sources", "prefers concise output"), and the quality standards the agent holds itself to.

**Leave out:** implementation details (tools, models, config), task-specific instructions (those go in the task description), and personality traits that don't affect output quality.

---

## 2. Agent Configuration Reference

`Agent` silently ignores keyword arguments it does not know, so a misspelled or removed parameter does nothing and raises nothing. Check `"name" in Agent.model_fields` when in doubt.

```python
Agent(
    role="...", goal="...", backstory="...",   # Required
    llm="anthropic/claude-haiku-4-5",          # See LLM Selection
    tools=[...],                               # Tool instances
    max_iter=25,             # Max reasoning iterations per task (default: 25)
    max_execution_time=300,  # Seconds, crew tasks only (default: None - no limit)
    max_rpm=10,              # Max LLM calls per minute for this agent (default: None)
    max_retry_limit=2,       # Retries when task execution errors (default: 2)
    allow_delegation=False,  # Default: False - agent works alone
    respect_context_window=True,  # Summarize and continue on overflow (default: True)
    inject_date=False,       # Put today's date in the prompt (default: False; format via date_format)
    verbose=False,           # Detailed execution logs (default: False)
)
```

### Execution limits (measured on 1.15.23)

| Limit | Behaviour |
|---|---|
| `max_iter` | Reaching it does **not** raise. The agent is told to give its final answer now, and the run "succeeds" with whatever it has. With `max_iter=1`, a four-step tool procedure recorded one step and returned an incomplete answer. |
| `max_rpm` | Calls over the limit block until the next minute window. With `max_rpm=2`, the third LLM call started at 62 s instead of about 2 s. |
| `max_execution_time` | Applies only when the agent runs a `Task` inside a `Crew`; `Agent.kickoff()` ignores it (a 5 s limit with a 15 s tool completed normally after 17 s). In a crew it does **not** stop work at the deadline: the running tool and LLM calls finish, then the task raises `TimeoutError: Task '...' execution timed out after 5 seconds` (raised at 18.8 s), and the finished work is discarded. |

So `max_execution_time` turns a slow run into an error but does not stop a hang. To bound wall-clock time, set timeouts where the time is spent: `LLM(model=..., timeout=60)` and timeouts inside your tools, or run the kickoff in a subprocess you can kill.

**Tuning `max_iter`:** the default 25 is generous - most tasks finish in 3-8 iterations. Lower it to 10-15 to fail faster when tasks are well-defined. If an agent keeps hitting it, the task is too vague (fix the task, not the limit). Hitting it does not raise, so check outputs, not exit codes.

**Other switches:** `respect_context_window=True` summarizes the conversation and continues when the provider reports that the context length was exceeded; with `False` the run stops with `SystemExit: Context length exceeded ...`. `inject_date=True` is worth it for time-sensitive tasks (research, news, scheduling): asked for today's date, an agent with it answered correctly, and one without it answered UNKNOWN.

### Tools

- An agent with **no tools** will hallucinate data when asked to search, fetch, or read files - always provide tools for tasks that require external data.
- Prefer **fewer, focused tools** - too many tools confuses the agent.
- Agent-level tools are available for all tasks the agent performs. `Task(tools=[...])` **replaces** them for that task. In a live test, an agent with a weather tool given a task with only a population tool could call only the population tool.
- Prebuilt tools need their keys (`SerperDevTool()` needs `SERPER_API_KEY`). Custom tools, the `crewai_tools` names that really exist, caching and MCP servers: **connect-tools-and-mcp**.

### LLM Selection

```python
from crewai import LLM

Agent(..., llm="anthropic/claude-haiku-4-5")
Agent(..., llm=LLM(model="anthropic/claude-haiku-4-5", temperature=0.2, timeout=60))
```

- With no `llm=`, the agent uses env `MODEL`, then `MODEL_NAME`, then `OPENAI_MODEL_NAME`, else `gpt-4.1-mini`. That is an OpenAI model, so kickoff fails without `OPENAI_API_KEY`.
- Only OpenAI ships with core crewai. `anthropic/...` needs `uv add "crewai[anthropic]"`, `gemini/...` needs `crewai[google-genai]`, and non-native providers need `crewai[litellm]` (full table in **check-crewai-api**).
- Give mechanical agents a cheaper model. `function_calling_llm` (a separate model for tool calls) is deprecated on both `Agent` and `Crew` - set each agent's `llm` instead.

### Collaboration

Set `allow_delegation=True` only when the agent is part of a crew with other specialized agents, the task genuinely benefits from handing off subtasks, or you're using hierarchical process where the manager delegates. **Warning:** delegation without clear task boundaries leads to infinite loops or wasted iterations.

### Planning (Plan-and-Execute Mode)

With a `PlanningConfig`, the agent first generates a plan (a list of steps), executes each step in its own multi-turn loop (capped by `max_step_iterations`), checks each result, then continues, replans, or finishes early.

```python
from crewai import Agent
from crewai.agent.planning_config import PlanningConfig

agent = Agent(
    role="…", goal="…", backstory="…", tools=[...],
    planning_config=PlanningConfig(reasoning_effort="medium"),  # most common
)
```

To disable planning, omit `planning_config`. `planning=True` alone is shorthand for `PlanningConfig(reasoning_effort="low", max_attempts=1)`. `reasoning=True` is deprecated (DeprecationWarning) - use `planning_config`.

| `reasoning_effort` | After each step the planner... | Pick when |
|---|---|---|
| `"low"` | checks the step with a heuristic (**no extra LLM call**) and continues. No replan, no refine. | You want plan visibility (todos, observations) but trust the agent to follow it linearly. Fastest. |
| `"medium"` (default) | observes the step with an LLM call; **replans on failure only**. | The agent's tools can fail (network, exec, scrape) and you want graceful recovery. **The right default for sandbox-coding, research, and other tool-heavy loops.** |
| `"high"` | observes, then can finish early, replan fully, or refine the plan after every step. | The task changes shape based on intermediate findings, or you need maximum adaptiveness. Most LLM calls per run. |

```python
PlanningConfig(
    reasoning_effort="medium",
    observe_steps=None,      # None = LLM observation for medium/high, heuristic for low
    max_steps=20,            # cap on planned steps
    max_replans=3,           # full re-plans before finalizing
    max_attempts=None,       # refinement attempts during plan generation
    max_step_iterations=15,  # LLM turns per step
    step_timeout=None,       # wall-clock seconds per step
    system_prompt=None, plan_prompt=None, refine_prompt=None,  # custom prompts
    llm=None,                # separate (cheaper) LLM for planning; else agent.llm
)
```

**When to enable:** for autonomous loops where the agent picks its own steps and you want failure recovery (a coding agent that writes → runs → patches; a research agent that searches → scrapes → revises). **Skip** it for single-tool, single-purpose calls ("summarize this string", "post this Slack DM").

**Cost (measured):** a two-tool arithmetic task ("multiply, then add") on `claude-haiku-4-5` took **3** LLM calls without planning, **6** with `"low"`, **7** with `planning=True` and **10** with `"medium"`. The medium run also repeated a completed step and reported a wrong total, and both planned runs wrapped the answer in prose about the plan. Planning multiplies calls on small tasks and can make them worse - measure before turning it on, and before defaulting to `high`.

### Code Execution

`allow_code_execution` and `code_execution_mode` are deprecated no-ops (`allow_code_execution=True` emits a DeprecationWarning), and `CodeInterpreterTool` no longer exists in `crewai_tools`. Give the agent a sandbox tool such as `E2BPythonTool` or `DaytonaPythonTool` instead (see **connect-tools-and-mcp**).

### Agent Guardrails

```python
from typing import Any

def require_uppercase(result) -> tuple[bool, Any]:
    if result.raw != result.raw.upper():
        return (False, "Rewrite the whole answer in UPPERCASE letters only.")
    return (True, result.raw)

agent = Agent(..., guardrail=require_uppercase, guardrail_max_retries=3)  # default retries: 3
result = agent.kickoff("...")   # the agent guardrail runs here
```

A guardrail can also be a string, which is checked by an extra LLM call. Agent guardrails have two limits on 1.15.23, both verified with a real LLM:
- **They run only on `Agent.kickoff()`.** When the same agent executes a `Task` in a `Crew`, the agent guardrail is never called.
- **The retry does not pass your feedback to the LLM.** The retried call sends the same messages as the first, so the agent cannot learn what was wrong: three attempts all failed the uppercase check above. When retries run out, `kickoff` raises `ValueError: Agent's guardrail failed validation after N retries. Last error: ...`.

When output must be fixed and not just rejected, put the guardrail on the **Task** (`Task(guardrail=..., guardrail_max_retries=...)`). The error message is fed back there, and the same uppercase check passed on the second attempt. See `design-task` and **check-crewai-api**.

### Knowledge Sources

```python
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

Agent(
    ...,
    knowledge_sources=[TextFileKnowledgeSource(file_paths=["company_handbook.txt"])],  # read from ./knowledge/
    embedder={"provider": "onnx"},   # local, no API key; omit it to use OpenAI embeddings
)
```

Knowledge sources give agents domain-specific data via RAG. Use them when agents need to reference large documents, policies, or datasets. Two things to know:
- **Agent knowledge is only queried when the agent runs a task inside a `Crew`.** `Agent.kickoff()` silently ignores `knowledge_sources`. In a live test, the same agent answered "UNKNOWN" from `kickoff()` and correctly from a one-task crew.
- Without `embedder=`, knowledge uses OpenAI embeddings. With no `OPENAI_API_KEY`, agent knowledge raises `ValueError: Invalid Knowledge Configuration` at crew kickoff. Crew-level knowledge only logs `Failed to upsert documents` and runs **without** it.

Embedders that work without OpenAI, `KnowledgeConfig`, memory and storage paths: [references/memory-and-knowledge.md](references/memory-and-knowledge.md).

---

## 3. YAML Configuration (Recommended)

Define agents in `agents.yaml` for clean separation of config and code. Create a YAML project with `crewai create crew <name> --classic`. Without `--classic`, `crewai create crew` starts an interactive wizard that writes a JSON project instead.

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
  # Optional overrides: llm: anthropic/claude-haiku-4-5, max_iter: 15, max_rpm: 10,
  # allow_delegation: false, verbose: true
```

Then wire in `crew.py`:

```python
@CrewBase
class MyCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config["researcher"], tools=[SerperDevTool()])
```

**Critical:** The method name (`def researcher`) must match the YAML key (`researcher:`). Mismatch causes `KeyError` (verified: `KeyError: 'researcher'`).

Verified live: `llm` and `max_iter` set in YAML are applied, `{topic}` in the role is filled at kickoff, and tools attach in Python. Keep tools, guardrail functions and Pydantic models in Python; YAML holds the text and scalar settings.

---

## 4. Agent.kickoff() - Direct Agent Execution

Use `Agent.kickoff()` when you need one agent with tools and reasoning, without crew overhead. This is the most common pattern in Flows. It does not use the agent's knowledge sources or `max_execution_time` (Section 2).

```python
from pydantic import BaseModel
from crewai import Agent

researcher = Agent(
    role="Senior Research Analyst",
    goal="Find comprehensive, factual information with source citations",
    backstory="Expert researcher known for thorough, evidence-based analysis.",
    tools=[...],
    llm="anthropic/claude-haiku-4-5",
)

result = researcher.kickoff("What are the latest developments in quantum computing?")
print(result.raw)             # str - the agent's full response
print(result.usage_metrics)   # dict: total_tokens, prompt_tokens, completion_tokens, ...

class ResearchFindings(BaseModel):
    key_trends: list[str]
    sources: list[str]
    confidence: float

result = researcher.kickoff("Research the latest AI agent frameworks", response_format=ResearchFindings)
print(result.pydantic.key_trends, result.pydantic.confidence)

result = await researcher.kickoff_async("...", response_format=ResearchFindings)  # async variant
```

> **Note:** `Agent.kickoff()` returns `LiteAgentOutput` - access structured output via `result.pydantic`. This differs from `llm.call(messages, response_model=Model)`, which returns the Pydantic object directly. `Agent.kickoff(..., response_model=...)` is a `TypeError`.

**File inputs** need an extra: `uv add "crewai[file-processing]"`, then `from crewai_files import FileInput` and `researcher.kickoff("Summarize this document", input_files={"document": FileInput(path="report.pdf")})`. Without the extra, the import fails with `ModuleNotFoundError: No module named 'crewai_files'`.

**Agent.kickoff() vs Crew.kickoff():** use `Agent.kickoff()` when each step is a distinct agent and a Flow controls sequencing (the Section 0 shape - verified live as a two-step Flow). Use `Crew.kickoff()` when multiple agents collaborate on related tasks within a single step, or the agent needs knowledge sources or `max_execution_time`.

### Agents in Conversational Flow Routes

In conversational Flows (`from crewai.flow import ConversationState`), the Flow owns the chat lifecycle and route selection. Call agents inside route handlers for bounded tool-backed work: research, docs lookup, account actions, triage, drafting, or escalation prep. The mechanics (`handle_turn`, `ConversationConfig`, a tested example) are in the **build-flow** skill's conversational-flows reference.

Design implications:
- Keep the conversational `Flow` responsible for session id, message history, routing, trace finalization, and approvals.
- Keep each agent narrow: one route, one tool surface, one job.
- Use `self.append_agent_result(name, result, visibility="private")` for scratch work that should not enter canonical chat history.
- Return the user-visible reply from the handler (or call `self.append_assistant_message(reply)`) so the next turn has the assistant context.
- Do not make a "chat agent" with every tool. Route first, then invoke a focused agent for the selected route.

---

## 5. Specialist vs Generalist Agents

> Apply this section *after* you've decided you genuinely need multiple agents (Section 0). With one agent, the only question is how to design that agent.

**When you do need multiple agents, prefer specialists.** An agent that does one thing well outperforms one that does many things acceptably. Use a specialist when the task needs deep domain knowledge, quality matters more than speed, or the task is complex enough to benefit from focused expertise. A generalist is acceptable for simple tasks with clear instructions, for prototyping you'll specialize later, and for tasks that truly span several domains equally.

Instead of one "Content Writer" agent, create `technical_writer` (technical accuracy, code examples), `copywriter` (persuasive, audience-focused copy) and `editor` (grammar, consistency, style guide). Each has a narrow role, specific goal, and a backstory that reinforces that expertise.

---

## 6. Agent Interaction Patterns

**Sequential (default):** `Researcher → Writer → Editor`. Agents work one after another, and each receives prior outputs as context. Best for linear pipelines where each step builds on the last.

**Hierarchical:** a manager agent delegates and validates; task assignment is dynamic. Best for complex workflows where assignment depends on intermediate results.

```python
Crew(
    agents=[researcher, writer, editor],
    tasks=[research_task, writing_task, editing_task],
    process=Process.hierarchical,
    manager_llm="anthropic/claude-haiku-4-5",   # or manager_agent=...; one is required
)
```

Without `manager_llm` or `manager_agent`, `Crew(...)` raises a `ValidationError`.

**Agent-to-agent delegation:** with `allow_delegation=True`, an agent gets two tools, `Delegate work to coworker` and `Ask question to coworker`, that name the other crew members. Verified live: asked to get a sentence from the Writer, a lead agent called `ask_question_to_coworker` and returned the Writer's answer.

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
| No guardrail on critical output | Bad output passes through unchecked | Add a Task guardrail for outputs that feed into production systems |
| Agent guardrail on an agent used in a Crew | Guardrail never runs | Put the guardrail on the Task |
| Trusting `max_execution_time` to stop a hang | It raises only after the slow call returns, and `Agent.kickoff()` ignores it | Add LLM and tool timeouts |
| Knowledge sources on an agent run via `Agent.kickoff()` | Knowledge silently unused | Run it as a crew task, or put the facts in the prompt |
| No `llm=` and no OpenAI key | Kickoff fails: the default is OpenAI `gpt-4.1-mini` | Set `llm=` (or env `MODEL`) and install the provider extra |
| Planning on a simple task | 2-3x the LLM calls, sometimes a worse answer | Enable planning only for open-ended tool loops |

---

## 8. Agent Design Checklist

Before deploying an agent, verify:

- [ ] **Role** is specific and domain-focused (not "Assistant" or "Helper")
- [ ] **Goal** includes desired outcome AND quality standards
- [ ] **Backstory** establishes expertise and working style
- [ ] **Tools** are assigned for any task requiring external data
- [ ] **No excess tools** - 3-5 per agent maximum
- [ ] **max_iter** is tuned for expected task complexity (10-15 for simple, 20-25 for complex)
- [ ] **Timeouts** are set where time is spent (LLM `timeout`, tool timeouts); `max_execution_time` is only a backstop for crew tasks
- [ ] **Guardrails** for critical outputs are on the Task
- [ ] **LLM** is set explicitly, fits the task's complexity, and has its provider extra installed
- [ ] **Knowledge** has an explicit `embedder`, and the agent runs inside a crew
- [ ] **Delegation** is disabled unless genuinely needed

---

## References

For deeper dives into specific topics, see:

- [Custom Tools](references/custom-tools.md) - building your own tools with `@tool` decorator and `BaseTool` subclass
- [Memory & Knowledge](references/memory-and-knowledge.md) - memory, knowledge sources, embedders that work without OpenAI, storage, scoping

For related skills:

- **check-crewai-api** - current imports, parameters, defaults and provider extras
- **connect-tools-and-mcp** - custom tools, real `crewai_tools` names, caching, MCP servers
- **build-flow** - Flow state, routing, persistence, conversational flows
- **getting-started** - project scaffolding, choosing the right abstraction
- **design-task** - task description/expected_output best practices, guardrails, structured output, dependencies
- **test-crewai-project** - testing agents and crews offline with a stub LLM
- **ask-docs** - query the live CrewAI docs for questions not covered by these skills
