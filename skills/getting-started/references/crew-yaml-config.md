# Crew YAML Configuration and `@CrewBase`

Full `agents.yaml`, `tasks.yaml` and `crew.py` examples for the classic crew layout - the `crews/<name>/` folder inside a `crewai create flow` project, or a `crewai create crew <name> --classic` project.

Verified against crewai 1.15.23 on 2026-10-01: the YAML and `crew.py` below load as written (two agents, two tasks, `reporting_task.context` set), and the scaffolded classic crew of the same researcher / reporting_analyst shape ran end to end with `anthropic/claude-haiku-4-5` via `crewai run`.

---

## 1. YAML Configuration (agents.yaml & tasks.yaml)

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
- `expected_output` is always a **string** (never a Pydantic class name); set `output_pydantic=Model` in the `@task` method in Python
- `agent` value must match an agent key in `agents.yaml`
- In `Process.sequential`, each task auto-receives all prior task outputs as context
- For non-sequential deps, use `context=[other_task]` to explicitly pass output

---

## 2. Wiring It Together - crew.py

The `@CrewBase` decorator auto-loads YAML config files and collects `@agent` and `@task` methods.

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

@CrewBase
class ResearchCrew:
    """Research and reporting crew."""

    agents_config = "config/agents.yaml"   # these two paths are also the defaults
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

Structured output stays in Python: `Task(config=self.tasks_config["research_task"], output_pydantic=Report)`. An `output_pydantic:` key in `tasks.yaml` is not a substitute (see the **check-crewai-api** skill).
