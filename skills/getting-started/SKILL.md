---
name: getting-started
description: "CrewAI architecture decisions and project scaffolding. Use when starting a new crewAI project, choosing between LLM.call() vs Agent.kickoff() vs Crew.kickoff() vs Flow, scaffolding with 'crewai create flow', setting up YAML config (agents.yaml, tasks.yaml), wiring @CrewBase crew.py, writing Flow main.py with @start/@listen, building experimental conversational Flows with handle_turn()/chat(), or using {variable} interpolation."
---

# CrewAI Getting Started & Architecture

How to choose the right abstraction, scaffold a project, and wire everything together.

Verified against crewai 1.15.23 on 2026-10-01.
Live-tested with real LLMs (`anthropic/claude-haiku-4-5`) on 2026-10-01.
Run `crewai version` first; if the major/minor differs from 1.15, re-check version-sensitive details with the `ask-docs` skill.

---

## MANDATORY WORKFLOW - Read This First

**NEVER manually create crewAI project files.** Always scaffold with the CLI:

```bash
crewai create flow <project_name>
```

This is **not optional**. Even if you only need one crew, even if you know the file structure by heart - run the CLI first, then modify the generated files. Do NOT write `main.py`, `crew.py`, `agents.yaml`, `tasks.yaml`, or `pyproject.toml` by hand from scratch.

> **Why:** The CLI sets up correct imports, directory structure, pyproject.toml config, and boilerplate that is easy to get subtly wrong when done manually. The reference material below teaches you how the pieces work so you can *modify* scaffolded code, not so you can *replace* the scaffolding step.

**Workflow:**
1. Run `crewai create flow <name>` (prefer **underscores**; the CLI turns hyphens and spaces into underscores for the folder and package)
2. Edit the generated YAML and Python files to match your use case
3. Run `crewai install` then `crewai run`

---

## 1. Choosing the Right Abstraction

crewAI has five common abstraction choices. Pick the simplest one that fits your need:

| Level | When to Use | Overhead | Example |
|---|---|---|---|
| `LLM.call()` | Single prompt, no tools, structured extraction | Lowest | Parse an email into fields |
| `Agent.kickoff()` | One agent with tools and reasoning, no multi-agent coordination | Low | Research a topic with web search |
| `Crew.kickoff()` | Multiple agents collaborating on related tasks | Medium | Research + write + review pipeline |
| `Flow` wrapping crews/agents/LLM calls | Production app with state, routing, conditionals, error handling | Full | Multi-step workflow with branching logic |
| Conversational `Flow` | Multi-turn chat where each user line re-runs a Flow with the same session id | Full + experimental | Support assistant with routed chat, research, and escalation turns |

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

Do users send multiple chat messages in one session?
└── Yes → Conversational Flow with handle_turn(message, session_id=...)
```

**Rule of thumb:** For any production application, **always start with a Flow**. You can embed `LLM.call()`, `Agent.kickoff()`, or `Crew.kickoff()` inside Flow steps. This gives you state management, error handling, and room to grow.

For chat applications, start with a conversational `Flow` rather than trying to make `Crew.kickoff()` or `Flow.kickoff()` act like a chat loop: call `flow.handle_turn(message, session_id=...)` for every user line, or `flow.chat()` for a local terminal REPL. Official guide: <https://docs.crewai.com/en/guides/flows/conversational-flows>.

---

## 2. LLM.call() - Direct LLM Invocation

Use for simple, single-turn tasks where you don't need tools or agent reasoning.

```python
from crewai import LLM
from pydantic import BaseModel

class EmailFields(BaseModel):
    sender: str
    subject: str
    urgency: str

llm = LLM(model="openai/gpt-4o")   # non-OpenAI providers need their extra, e.g. uv add "crewai[anthropic]"

# Plain call - returns a string
raw = llm.call(messages=[{"role": "user", "content": "Summarize this text..."}])
print(raw)  # str

# With response_model - returns the Pydantic object directly
result = llm.call(
    messages=[{"role": "user", "content": f"Extract fields from this email: {email_text}"}],
    response_model=EmailFields,
)
print(result.sender)   # str - access Pydantic fields directly
print(result.urgency)  # str
```

> `llm.call(..., response_format=Model)` raises `TypeError: ... unexpected keyword argument 'response_format'. Did you mean 'response_model'?`. On `LLM.call()` the keyword is `response_model`; on `Agent.kickoff()` it is `response_format` (next section).

**When NOT to use:** If you need tools, multi-step reasoning, or retries - use an Agent instead.

---

## 3. Agent.kickoff() - Single Agent Execution

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
    llm="openai/gpt-4o",       # Optional: defaults to the MODEL / MODEL_NAME / OPENAI_MODEL_NAME env var, else "gpt-4.1-mini"
    tools=[SerperDevTool()],   # needs SERPER_API_KEY
)

# Unstructured output
result = researcher.kickoff("What are the latest LLM developments?")
print(result.raw)            # str
print(result.usage_metrics)  # token usage dict

# Structured output with response_format
result = researcher.kickoff(
    "Summarize latest AI developments",
    response_format=ResearchFindings,
)
print(result.pydantic.main_points)
```

> **Note:** `Agent.kickoff()` wraps results in a `LiteAgentOutput` - access structured output via `result.pydantic`. This differs from `LLM.call()`, which returns the Pydantic object directly.

**When NOT to use:** If you need multiple agents passing context to each other - use a Crew.

---

## 4. CLI Scaffold Reference

As stated above: **NEVER skip `crewai create flow`.** This section documents what the CLI generates so you know what to modify - not so you can recreate it by hand.

```bash
crewai create flow my_project
```

> **Naming:** `crewai create flow my-project` still works - the CLI creates the folder and package as `my_project` - but use underscores so the name you type matches the package you import.

This generates (crewai 1.15.23):

```
my_project/
├── src/my_project/
│   ├── crews/
│   │   └── content_crew/
│   │       ├── config/
│   │       │   ├── agents.yaml    # Agent definitions (role, goal, backstory)
│   │       │   └── tasks.yaml     # Task definitions (description, expected_output)
│   │       └── content_crew.py    # Crew class with @CrewBase
│   ├── tools/
│   │   └── custom_tool.py
│   └── main.py                    # Flow class with @start/@listen, plus kickoff() and plot()
├── .env                           # OPENAI_API_KEY placeholder - replace it, never commit it
├── AGENTS.md, CLAUDE.md, GEMINI.md, CURSOR.md   # coding-assistant instructions
├── README.md
└── pyproject.toml                 # [tool.crewai] type = "flow"; scripts kickoff, plot, ...
```

The scaffold depends on `crewai[tools]` only - neither `crewai create flow` nor `crewai create crew --classic` adds a provider extra, so for any non-OpenAI model run `uv add "crewai[anthropic]"` (or the matching extra) before `crewai install`.

The generated `main.py` imports with the absolute package path - `from my_project.crews.content_crew.content_crew import ContentCrew` - and `from crewai.flow import Flow, listen, start`. Keep that style; relative imports (`from .crews...`) break `uv run src/my_project/main.py` and fail `crewai deploy validate` (see the **deploy-to-amp** skill). Keep `kickoff()` in `main.py` returning `None`: the console script does `sys.exit(kickoff())`, so returning the result makes the process exit 1. More on the flow scaffold: the **build-flow** skill.

> **Prefer `crewai create flow`.** Use `crewai create crew <name> --classic` only if you are certain you will never need routing, state, or multiple crews. Without `--classic`, `crewai create crew` starts an interactive wizard that writes a JSON project (`crew.jsonc`, `agents/*.jsonc`) instead of the `@CrewBase` + YAML layout below, and with no terminal it prints `Aborted!`. Add `--skip-provider` to skip the provider prompt in scripts.

---

## 5. Crews: YAML Config and `@CrewBase`

The scaffold defines agents and tasks in YAML and wires them in a `@CrewBase` class. Full two-agent examples: [Crew YAML Configuration](references/crew-yaml-config.md).

```yaml
# config/agents.yaml
researcher:
  role: >
    {topic} Senior Data Researcher
  goal: >
    Uncover cutting-edge developments in {topic}
  backstory: >
    You're a seasoned researcher with a knack for uncovering
    the latest developments in {topic}.
  # Optional overrides: llm: openai/gpt-4o, max_iter: 20, max_rpm: 10

# config/tasks.yaml
research_task:
  description: >
    Conduct thorough research about {topic}.
  expected_output: >
    A detailed report on the top 5 developments in {topic}.
  agent: researcher
  output_file: output/report.md
```

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

@CrewBase
class ResearchCrew:
    """Research crew."""

    agents_config = "config/agents.yaml"   # these two paths are also the defaults
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:          # method name == YAML key
        return Agent(config=self.agents_config["researcher"])

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
```

**Key rules:**
- `{variable}` placeholders are replaced at runtime via `crew.kickoff(inputs={...})`
- `expected_output` is always a **string** (never a Pydantic class name); set `output_pydantic=Model` in the `@task` method in Python
- `agent` value must match an agent key in `agents.yaml`, and method names must match YAML keys (`def researcher` -> `researcher:`)
- In `Process.sequential`, each task auto-receives all prior task outputs as context
- For non-sequential deps, use `context=[other_task]` to explicitly pass output

---

## 6. Flows - The Production Foundation

Flows are the recommended way to build production crewAI applications. They provide state management, conditional routing, human-in-the-loop, and persistence - wrapping crews, agents, and LLM calls into a coherent workflow. This section covers how the abstractions fit together; for the full Flow API (state rules, `or_`/`and_`, `@persist`, checkpoints, `@human_feedback`, `plot()`) use the **build-flow** skill.

### Basic Flow - main.py

```python
from crewai.flow import Flow, listen, start
from pydantic import BaseModel
from my_project.crews.research_crew.research_crew import ResearchCrew

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
    flow.kickoff(inputs={"topic": "AI Agents"})   # do not return the result

if __name__ == "__main__":
    kickoff()
```

**Key points:**
- `flow.kickoff(inputs={"topic": "AI Agents"})` populates `self.state.topic` (keys must match Pydantic field names; unknown keys are silently dropped). The YAML `{variable}` substitution happens later, when you call `crew.kickoff(inputs={"topic": self.state.topic})` inside a Flow step. The chain is: **flow inputs → state → crew inputs → YAML substitution**.
- Each `@listen` method runs after its dependency completes
- State persists across all Flow steps - use it to pass data between crews

**State:** use structured state (`Flow[MyState]` with a Pydantic model, every field defaulted) for type safety and validation; `class MyFlow(Flow)` gives dict state (`self.state["topic"]`) for throwaway prototypes. Do not declare `id` yourself - the Flow adds it.

### Using Agent.kickoff() Inside Flows (Common Pattern)

Many production Flows skip Crews entirely and orchestrate individual agents via `Agent.kickoff()`. This gives you fine-grained control - each Flow step builds a purpose-built agent (narrow role, specific tools), passes it state, and stores `result.raw` (or `result.pydantic` with `response_format=Model`) back on state. The Flow handles orchestration; agents handle reasoning. The `handle_simple` step in the next example is this pattern.

**When to use Agent.kickoff() vs Crew.kickoff() in a Flow:**

| Use `Agent.kickoff()` when | Use `Crew.kickoff()` when |
|---|---|
| Each step is a distinct agent with different tools | Multiple agents need to collaborate on ONE task |
| You want the Flow to control sequencing | Agents need to pass context to each other within a step |
| Steps are independent and don't need inter-agent delegation | You need hierarchical process with a manager |
| You want maximum control over what data flows between steps | The sub-workflow is self-contained and reusable |

### Mixing Abstractions in a Flow

A Flow can combine all crewAI abstractions in a single workflow:

```python
from crewai import LLM, Agent
from crewai.flow import Flow, listen, router, start

class ProductFlow(Flow[ProductState]):

    @start()
    def classify_request(self):
        # LLM.call() for simple classification
        llm = LLM(model="openai/gpt-4o")
        self.state.category = llm.call(
            messages=[{"role": "user", "content": f"Classify as 'simple' or 'complex': {self.state.request}"}],
            response_model=Category,
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
        self.state.answer = agent.kickoff(self.state.request).raw

    @listen("deep_research")
    def handle_complex(self):
        # Crew.kickoff() for multi-agent collaboration
        result = ResearchCrew().crew().kickoff(
            inputs={"topic": self.state.request}
        )
        self.state.answer = result.raw
```

### Routing, Joins, Persistence, Human Feedback - the Short Version

- **`@router(method)`** returns a string label; `@listen("label")` runs that branch. A label must not equal the name of the method that listens for it, and every label needs a listener (an unmatched label ends the flow silently).
- **`or_(a, b)`** fires **once**, on the first condition to complete. **`and_(a, b)`** fires once after all complete. Import both from `crewai.flow`.
- **`@persist()`** (with parentheses; `from crewai.flow import persist`) saves state to a local SQLite file; resume with `kickoff(restore_from_state_id=...)`.
- **`@human_feedback(message=..., emit=[...], llm=..., default_outcome=...)`** pauses for review and routes on the outcome. The reviewer's text is `result.feedback` on the `HumanFeedbackResult` (or `self.last_human_feedback.feedback`).
- **`flow.plot("my_flow.html", show=False)`** writes interactive HTML into a temp directory and returns its path - no PNG.

Tested patterns for each are in [Flow Routing](references/flow-routing.md) and the **build-flow** skill.

### Conversational Flows with `handle_turn()`

Use a conversational `Flow` when the product is a chat session: support assistants, routed research helpers, onboarding wizards, or any UI where the same user sends multiple turns.

Core model:
- Each user message is a **new Flow run** with the **same session id**
- `handle_turn(message, session_id=...)` appends the user line to `state.messages`, resets per-turn execution tracking, and calls `kickoff(inputs={"id": session_id})` internally
- `Flow.kickoff()` does **not** accept `user_message=` or `session_id=` keyword args (`TypeError`)
- Route chat turns with `route_turn()` plus `@listen("ROUTE")` handlers, or leave `route_turn()` out and let the LLM router pick from your handlers
- A string a handler returns becomes the assistant reply; call `append_assistant_message(reply)` when you want to record it explicitly (it is not duplicated)
- Wrap owned loops in `try/finally` and call `finalize_session_traces()`; `flow.chat()` does this for local REPLs

Import from `crewai.flow`; `crewai.experimental.conversational` is a deprecated alias of the same module. The `@ConversationConfig` decorator already sets `conversational = True` and `defer_trace_finalization` defaults to `True`. Without an `llm`, the `converse` route replies "I can continue the conversation once an LLM is configured."

For LLM-driven routing you need no extra config: with `@ConversationConfig(llm=...)` and no `route_turn()`, the router auto-enables and builds its catalog from `@listen("ROUTE")` handlers and their docstrings - do not duplicate the route list in a router prompt. Pass a `RouterConfig` only to change the prompt, descriptions, or fallback.

A minimal, tested example (`route_turn()` with a custom handler plus `converse`, driven by `handle_turn()` in `try/finally`) and the full lifecycle, routing, streaming, persistence, and trace guidance are in [Conversational Flows](references/conversational-flows.md).

---

## 7. Variable Interpolation with `inputs`

The `{variable}` pattern is how you make crews reusable.

```python
# Variables flow through: kickoff → YAML templates → agent/task prompts
crew.kickoff(inputs={
    "topic": "AI Agents",
    "current_year": "2025",
    "target_audience": "developers",
})
```

In YAML, `{topic}` and `{current_year}` get replaced (in agent `role`/`goal`/`backstory` as well as task `description`/`expected_output`):

```yaml
research_task:
  description: >
    Research {topic} trends for {current_year},
    targeting {target_audience}.
```

**Common mistakes:**
- Calling `kickoff()` with **no** `inputs` → the literal `{variable}` goes into the prompt
- Passing `inputs` that miss a variable referenced in YAML → `ValueError: Missing required template variable 'Template variable 'current_year' not found in inputs dictionary'`
- Using Jinja2 syntax `{{ }}` instead of single-brace `{ }` → crewAI uses single braces; `{{ topic }}` stays literal
- Passing variables that don't match any YAML placeholder → silently ignored

---

## 8. Running Your Project

```bash
# Install dependencies
crewai install

# Run the flow (or classic crew)
crewai run
```

Or run directly from the project directory:

```bash
cd my_project
uv run kickoff                  # flow: the console script in pyproject.toml (run_crew for a classic crew)
uv run src/my_project/main.py   # also works with the scaffold's absolute imports
```

Model and keys come from the environment or `.env`: set `MODEL=anthropic/claude-haiku-4-5` (or any provider string) plus that provider's key, and add the provider extra with `uv add "crewai[anthropic]"`. With no `MODEL` and no `llm=`, agents use `gpt-4.1-mini` and need `OPENAI_API_KEY`.

---

## 9. Quick Diagnostic Checklist

| Symptom | Likely Cause | Fix |
|---|---|---|
| `{topic}` appears literally in agent output | No `inputs=` in `kickoff()` | Pass `crew.kickoff(inputs={"topic": "..."})` |
| `ValueError: Missing required template variable` | `inputs` given but one YAML placeholder missing | Pass every `{variable}` the YAML uses |
| `KeyError` on `self.agents_config['name']` | Method name doesn't match YAML key | Ensure `@agent def researcher` matches `researcher:` in YAML |
| `ModuleNotFoundError` / `ImportError: attempted relative import` | Relative import, or a package path that doesn't match the folder | Use the scaffold's absolute form `from my_project.crews.crew_name.crew_name import CrewClass` |
| `ImportError: cannot import name 'persist'` | `from crewai.flow.flow import persist` | `from crewai.flow import persist` |
| `TypeError: ... unexpected keyword argument 'response_format'` from `llm.call` | Wrong keyword for `LLM.call()` | `llm.call(messages, response_model=Model)` |
| Crew runs but Flow state is empty | Not writing results back to `self.state` | Assign crew output to `self.state.field` in the `@listen` method |
| `Process.SEQUENTIAL` raises `AttributeError` | Uppercase enum | Use lowercase: `Process.sequential` |
| Agent ignores tools | Tools assigned to agent but task needs them | Move tools to task level or verify agent has the right tools |
| Agent fabricates search results | No tools assigned - agent can't actually search | Add `tools=[SerperDevTool()]` or equivalent; an agent with no tools will hallucinate data |
| `@listen` never fires | Listener string doesn't match router return value, or a typo in `@listen("method_name")` | `@router` must return the exact string `@listen("label")` expects; for method chaining prefer `@listen(method_ref)` |
| A listener ran once though two upstreams finished | That is `or_` - it fires once, on the first to complete | Use `and_()` if you need all upstream steps to complete first |
| `crewai run` says the flow errored but output looks right | `kickoff()` in `main.py` returned a value | Return `None` |
| `crewai create crew` prints `Aborted!` or asks wizard questions | It is a JSON wizard without `--classic` | `crewai create crew <name> --classic` (or use `crewai create flow`) |
| `AuthenticationError`, `API key not found`, or `OPENAI_API_KEY is required` | Missing env var for the model's provider | Set the provider key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...) and `SERPER_API_KEY` for search tools in `.env` |
| `Anthropic native provider not available` | Provider extra not installed | `uv add "crewai[anthropic]"` (or the matching extra) |
| Agent retries endlessly on structured output | Pydantic model too complex for the LLM | Simplify the model, reduce nesting, or use a more capable `llm` |
| Agent loops to `max_iter` without finishing | Task description too vague or conflicting with `expected_output` | Make `expected_output` specific and achievable; lower `max_iter` to fail faster |
| `@router` return value ignored | Method not decorated with `@router` | Use `@router(condition)` not `@listen(condition)` for branching methods |
| `AttributeError: ... 'feedback_text'` | Old `HumanFeedbackResult` field name | `result.feedback` |
| `Flow.kickoff(user_message=..., session_id=...)` fails | Conversational kwargs are not accepted by `kickoff()` | Use `flow.handle_turn(message, session_id=...)` for chat messages |
| Chat history missing assistant replies | Handler neither returned a string nor recorded the reply | Return the reply string, or call `self.append_assistant_message(reply)` |

---

## References

For deeper dives into specific topics, see:

- [Crew YAML Configuration](references/crew-yaml-config.md) - full `agents.yaml`, `tasks.yaml` and `@CrewBase` `crew.py` examples
- [Flow Routing, Persistence, Streaming & Human Feedback](references/flow-routing.md) - `@router`, `or_()`, `and_()`, `@persist`, streaming, and `@human_feedback` patterns
- [Conversational Flows](references/conversational-flows.md) - multi-turn Flow API with `handle_turn()`, `stream_turn()`, `chat()`, `ConversationConfig`, router behavior, persistence, and tracing
- [MCP Servers](references/mcp-servers.md) - prefer official MCP servers over native tools; setup, DSL integration, and known official servers
- [Tools Catalog](references/tools-catalog.md) - common built-in tools with imports, env vars, and common combos (use as fallback when no MCP server exists)

For related skills:

- **build-flow** - full Flow API: state rules, routers, `or_`/`and_`, `@persist`, checkpoints, `@human_feedback`, `plot()`
- **check-crewai-api** - current Agent/Task/Crew/LLM API vs remembered 0.x forms
- **connect-tools-and-mcp** - custom tools, which `crewai_tools` names exist, `mcps=[...]` forms and timeouts
- **design-agent** - agent Role-Goal-Backstory framework, parameter tuning, tool assignment, memory & knowledge configuration
- **design-task** - task description/expected_output best practices, guardrails, structured output, dependencies
- **test-crewai-project** - running crews and flows offline with a stub LLM
- **deploy-to-amp** - project shape and entry points a CrewAI AMP deployment expects
- **ask-docs** - query the live CrewAI docs for questions not covered by these skills
