# CrewAI Skills

A collection of skills for AI coding agents that teach best practices for building with [CrewAI](https://docs.crewai.com). Skills follow the [Agent Skills](https://agentskills.io/) format.

## Available Skills

### getting-started

CrewAI architecture decisions and project scaffolding. Covers choosing the right abstraction (`LLM.call()` vs `Agent.kickoff()` vs `Crew.kickoff()` vs `Flow`), CLI scaffolding, YAML configuration, wiring `@CrewBase` crews, writing Flows with `@start`/`@listen`, and variable interpolation.

**Use when:**
- Starting a new CrewAI project
- Choosing between abstraction levels
- Scaffolding with `crewai create flow`
- Setting up agents.yaml and tasks.yaml
- Wiring crew.py or main.py
- Debugging common setup issues

### design-agent

CrewAI agent design and configuration. Covers the Role-Goal-Backstory framework, LLM selection, tool assignment, execution tuning (`max_iter`, `max_rpm`, `max_execution_time`), memory and knowledge sources, guardrails, and YAML vs code configuration.

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

## Installation

```bash
npx skills add crewAIInc/skills
```

## Skill Structure

Each skill contains:
- `SKILL.md` - Instructions for the agent
- `references/` - Supporting documentation (tools catalog, MCP servers, structured output patterns, etc.)

## License

MIT
