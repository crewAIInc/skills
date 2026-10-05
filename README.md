# CrewAI Skills

A collection of skills for AI coding agents that teach best practices for building with [CrewAI](https://docs.crewai.com). Skills follow the [Agent Skills](https://agentskills.io/) format.

## Available Skills

### getting-started

CrewAI architecture decisions and project scaffolding. Covers choosing the right abstraction (`LLM.call()` vs `Agent.kickoff()` vs `Crew.kickoff()` vs `Flow`), CLI scaffolding, YAML configuration, wiring `@CrewBase` crews, writing Flows with `@start`/`@listen`, conversational Flows with `handle_turn()`, variable interpolation, and starting points for MCP servers and built-in tools.

**Use when:**
- Starting a new CrewAI project
- Choosing between abstraction levels
- Scaffolding with `crewai create flow`
- Setting up agents.yaml and tasks.yaml
- Wiring crew.py or main.py
- Building experimental conversational Flows
- Debugging common setup issues

### design-agent

CrewAI agent design and configuration. Covers how many agents to use, the Role-Goal-Backstory framework, LLM selection, tool assignment, execution limits (`max_iter`, `max_rpm`, `max_execution_time`) and what each really does, planning, memory and knowledge sources with embedders that work without OpenAI, agent guardrails, and YAML vs code configuration.

**Use when:**
- Creating or configuring CrewAI agents
- Choosing role, goal, and backstory
- Assigning tools or selecting LLMs
- Tuning agent parameters
- Setting up knowledge sources or memory
- Debugging agent behavior

### design-task

CrewAI task design and configuration. Covers writing effective descriptions and expected output, task dependencies with `context`, structured output (`output_pydantic`, `output_json`, `output_file`), guardrails, human-in-the-loop review, and async execution.

**Use when:**
- Creating or configuring CrewAI tasks
- Writing task descriptions and expected output
- Setting up task dependencies
- Configuring structured output formats
- Adding guardrails or human review
- Debugging task execution issues

### ask-docs

Answers CrewAI questions from the official documentation, matched to the crewai version the user runs. Covers the two docs sites (the open-source framework and the CrewAI AMP platform), their `llms.txt` indexes, Markdown pages and docs MCP servers, how to read the docs for a specific release, and checking a docs snippet against the installed package before trusting it.

**Use when:**
- A CrewAI question is not covered by the other skills
- Another skill asks to re-verify a row for a different crewai version
- Setting up the CrewAI docs MCP server in a coding agent

### check-crewai-api

The current crewai 1.15.x API versus the 0.x API that coding assistants tend to remember. A "you probably wrote X, the current form is Y" table covering imports, Agent/Task/Crew parameters and defaults, kickoff variants, LLM model strings and provider extras, structured output, guardrails, unified Memory, knowledge embedders, the `crewai create crew` wizard, and removed features. Each row was checked against crewai 1.15.22 and 1.15.23, with a source reference for re-checking after an upgrade.

**Use when:**
- Writing, reviewing, or debugging any crewai code
- Before trusting remembered crewai syntax
- An import, keyword argument, or provider error appears that looks like a version mismatch

### build-flow

Building Flows on the current API: structured state and `state.id`, `@start`/`@listen`/`@router` wiring, `or_`/`and_` semantics, router labels versus method names, `@persist` and resuming with `restore_from_state_id`, checkpointing, `@human_feedback`, `plot()`, and calling crews and agents from flow methods.

**Use when:**
- Writing or debugging a `Flow` subclass
- A listener never fires, or fires twice
- Persisting, resuming, or checkpointing a flow

### connect-tools-and-mcp

Giving agents tools and MCP servers: custom `BaseTool` and `@tool`, which `crewai_tools` names really exist, caching and usage limits, `Agent(mcps=[...])` string and config forms, rewritten MCP tool names, `MCPServerAdapter`, timeouts, and what works once deployed.

**Use when:**
- Writing a custom tool or connecting an MCP server
- An agent never calls a tool, or `mcps=[...]` yields no tools
- An MCP server works locally but not after deploy

### test-crewai-project

Deterministic, offline testing of crews and flows with pytest, using a stub `BaseLLM` (included) that drives text, structured output, and tool calls with no API key. Covers asserting on the prompts crewai built, testing guardrails and routing, what `crewai test` really does, event listeners, and the exact tracing and telemetry environment variable values.

**Use when:**
- Writing tests for a crewai project or running them in CI
- Stubbing the LLM or writing a custom `BaseLLM`
- Debugging a run with event listeners or traces

### deploy-to-amp

Getting a crew or flow onto CrewAI AMP: the project shape the build expects, `crewai deploy validate`, the three deploy paths (CLI, GitHub, ZIP upload) and what each one actually uploads, environment variables per deployment, provider keys and extras, and machine-wide org selection.

**Use when:**
- Running `crewai deploy create`, `push`, or `validate`
- A deployment is Online but runs old code or old environment values
- A build fails on project shape, lockfile, or entry points

### call-deployed-crew

Calling a deployed crew or flow over HTTP: the token and URL, `GET /inputs`, `POST /kickoff` with an `{"inputs": {...}}` body, which inputs are required, polling `GET /status/{kickoff_id}` with a deadline, terminal states, webhooks, and writing crews that stay correct under repeated and concurrent kickoffs. Includes a tested Python client and curl equivalents.

**Use when:**
- Writing a client, backend, or frontend that calls a deployed crew
- A kickoff returns `422 "Missing inputs: ..."`, or a status poll never ends or says `NOT FOUND`
- One run's prompt shows another run's data

## Example prompts

Each skill loads on its own when a request matches its description. These prompts each triggered the intended skill in a fresh install:

| Skill | Try asking |
|---|---|
| `getting-started` | "I'm new to CrewAI. Help me set up my first project from scratch - install, create a crew, and run it locally." |
| `design-agent` | "I'm writing the role, goal and backstory for a CrewAI research analyst agent and it keeps going off-topic and looping. How should I write these fields and which agent settings should I set?" |
| `design-task` | "How should I write the description and expected_output for a CrewAI task so the output comes back as a validated Pydantic object, and should I use context to pass the previous task's result?" |
| `ask-docs` | "Where in the official CrewAI docs is the reference for the Crew class planning parameter, and is there an llms.txt I can point my editor at?" |
| `check-crewai-api` | "My crew.py fails with: ImportError: cannot import name 'BaseTool' from 'crewai_tools'. Also I set memory_config on the Crew. What is wrong?" |
| `build-flow` | "My Flow listener decorated @listen('summarize') on a method named summarize raises 'listen condition references the handler name'. How do I fix the router wiring?" |
| `connect-tools-and-mcp` | "I passed mcps=['https://mcp.example.com/mcp'] to my Agent; the stdio version worked locally but after deploy the agent never calls the MCP tool. Why?" |
| `test-crewai-project` | "How do I write pytest tests for my crew in CI without an OpenAI key? I keep getting ValueError: OPENAI_API_KEY is required." |
| `deploy-to-amp` | "crewai deploy push says Online but the deployment still runs my old code. What does push actually upload?" |
| `call-deployed-crew` | "I'm calling my deployed crew's /kickoff endpoint with {'topic': 'AI'} and get 422. What should the body be and how do I poll the result?" |

Every skill names the crewai release it was verified against. If `crewai version` reports a different major or minor version, the skill tells the assistant to re-check version-sensitive details with `ask-docs`.

## Installation

In [Claude Code](https://docs.claude.com/en/docs/claude-code), add this marketplace and install the plugin:

```
/plugin marketplace add crewAIInc/skills
/plugin install crewai-skills@crewai-plugins
```

The first command registers the marketplace from this repo's `.claude-plugin/marketplace.json`. The second installs the `crewai-skills` plugin from the `crewai-plugins` marketplace.

To pin to a specific branch or tag, append `#<ref>`:

```
/plugin marketplace add crewAIInc/skills#<branch-or-tag>
```

## Skill Structure

Each skill contains:
- `SKILL.md` - Instructions for the agent
- `references/` - Supporting documentation (crew YAML configuration, tools catalog, MCP servers, structured output patterns, API contracts, etc.)

## License

MIT
