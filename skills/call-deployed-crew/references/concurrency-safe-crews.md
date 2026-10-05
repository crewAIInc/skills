# Concurrency-Safe Crews

How to write a crew whose runs cannot read or overwrite each other's data, with the failures each rule prevents. Every "observed" result below was reproduced on crewai 1.15.22-1.15.23 with an offline stub LLM.

A deployed crew serves many kickoffs. Treat every Python object that exists outside one `kickoff()` call - module globals, class attributes, tool instances, a `Crew` object you keep around, caches filled at import time - as visible to other runs.

---

## 1. Never write to task or agent text at runtime

crewai interpolates inputs by writing into the `Task` and `Agent` objects. The first time a task is interpolated it saves the current `description` as its template, and every later run re-renders from that saved template. Text you append at runtime is either frozen into the template by the first run or silently thrown away by later ones.

Bad - per-run data appended to the description:

```python
from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, before_kickoff, crew, task


@CrewBase
class ReportCrew:
    @before_kickoff
    def add_customer(self, inputs):
        self.tasks[0].description += f" The customer is {inputs['customer']}."  # do not do this
        return inputs

    @agent
    def writer(self) -> Agent:
        return Agent(role="Writer", goal="Write reports", backstory="Precise.")

    @task
    def write(self) -> Task:
        return Task(description="Write about {topic}.", expected_output="A report.", agent=self.writer())

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks)


report = ReportCrew().crew()
report.kickoff(inputs={"topic": "bees", "customer": "acme"})
report.kickoff(inputs={"topic": "volcanoes", "customer": "globex"})
# Observed: the second run's prompt says "The customer is acme." and never mentions globex.
```

Good - the per-run value is a placeholder, and `@before_kickoff` only shapes the inputs:

```python
from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, before_kickoff, crew, task


@CrewBase
class ReportCrew:
    @before_kickoff
    def normalise(self, inputs):
        return {**inputs, "customer": inputs["customer"].strip().title()}

    @agent
    def writer(self) -> Agent:
        return Agent(role="Writer", goal="Write reports", backstory="Precise.")

    @task
    def write(self) -> Task:
        return Task(
            description="Write about {topic}. The customer is {customer}.",
            expected_output="A report.",
            agent=self.writer(),
        )

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks)


report = ReportCrew().crew()
report.kickoff(inputs={"topic": "bees", "customer": "acme"})
report.kickoff(inputs={"topic": "volcanoes", "customer": "globex"})
# Observed: each prompt names its own customer.
```

---

## 2. Keep tools stateless

`crew.copy()` - which `kickoff_for_each` and `akickoff_for_each` use for every input - copies agents and tasks but hands the copies the **same tool objects**. Any attribute a tool writes is shared by every run that uses that crew.

Bad:

```python
from crewai.tools import BaseTool


class LookupTool(BaseTool):
    name: str = "lookup"
    description: str = "Look a topic up."
    seen: list = []  # per-run data on a shared object

    def _run(self, query: str) -> str:
        self.seen.append(query)
        return f"results for {query} (seen so far: {self.seen})"
# Observed with kickoff_for_each over two inputs: the second run's tool output
# listed the first run's query.
```

Good - per-run values arrive as arguments, or from a `ContextVar` that each run sets for itself:

```python
import contextvars

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, after_kickoff, agent, before_kickoff, crew, task
from crewai.tools import BaseTool

CURRENT_CUSTOMER: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_customer", default=None)


class CustomerRecordTool(BaseTool):
    name: str = "customer_record"
    description: str = "Fetch the current customer's record."

    def _run(self, field: str = "summary") -> str:
        customer = CURRENT_CUSTOMER.get()
        if customer is None:
            raise RuntimeError("no customer set for this run")
        return f"{field} for {customer}"  # look it up in your own storage here


@CrewBase
class SupportCrew:
    @before_kickoff
    def bind_customer(self, inputs):
        CURRENT_CUSTOMER.set(inputs["customer"])
        return inputs

    @after_kickoff
    def unbind_customer(self, output):
        CURRENT_CUSTOMER.set(None)
        return output

    @agent
    def helper(self) -> Agent:
        return Agent(role="Support agent", goal="Help {customer}", backstory="Careful.",
                     tools=[CustomerRecordTool()])

    @task
    def answer(self) -> Task:
        return Task(description="Answer {customer}'s question: {question}",
                    expected_output="An answer.", agent=self.helper())

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks)
```

Observed: two `akickoff()` calls running at the same time on two `SupportCrew().crew()` objects each saw only their own customer inside the tool.

---

## 3. One `Crew` object, one run at a time

| Call pattern on a single `Crew` object | Observed on 1.15.22-1.15.23 |
|---|---|
| Two concurrent `akickoff()` | Second run raises `RuntimeError: Executor is already running. Cannot invoke the same executor instance concurrently.` |
| Two concurrent `kickoff_async()` (thread-based) | Nondeterministic: sometimes both finished; sometimes the second raised the same `RuntimeError`, and in a few of those the run that finished had used the other run's input in a later task's prompt |
| A fresh crew per run, concurrently | Both finish; each run's prompts contain only its own inputs |

The agents and tasks hold per-run state (interpolated text, the agent executor), so a `Crew` object is not a reusable, thread-safe service object.

When you host crews yourself (a web handler, a worker, a test), build the crew inside the request:

```python
from crewai import Agent, Crew, Task


def build_research_crew() -> Crew:
    researcher = Agent(role="Researcher", goal="Research {topic}", backstory="Careful.")
    collect = Task(description="Collect facts about {topic}.", expected_output="Facts.", agent=researcher)
    summarise = Task(description="Summarise the facts about {topic}.", expected_output="A summary.", agent=researcher)
    return Crew(agents=[researcher], tasks=[collect, summarise])


async def handle_request(topic: str) -> str:
    result = await build_research_crew().akickoff(inputs={"topic": topic})  # fresh objects per request
    return result.raw
```

With `@CrewBase` the equivalent is `ResearchCrew().crew().kickoff(inputs=...)` per request.

---

## 4. Other shared things

| Shared thing | Practice |
|---|---|
| Module-level caches, clients, counters | Clients (HTTP sessions, DB pools) are fine to share; per-run data is not. Connect lazily and reconnect on failure |
| Local files and relative paths | Use absolute paths from env vars; never assume a file written by one run is there for the next |
| Quotas, idempotency, audit records | Keep them in storage you own; claim daily quota under a lock or a transactional update |
| External rate limits | Concurrent runs share them; wait on per-minute limits instead of failing |
| Memory-heavy work | Stream or chunk large inputs; measure peak memory locally first |
| `input()` | Never in a deployed crew; use `human_input=True` + `POST /resume`, or a Flow with `@human_feedback` |

---

## 5. Test it before you deploy

Run two different inputs through the code path your server uses and assert that neither prompt contains the other's data. With an offline stub LLM (see the `test-crewai-project` skill) the prompts are recorded on the stub:

```python
import asyncio

from crewai import Agent, Crew, Task


def build(llm) -> Crew:
    a = Agent(role="Researcher", goal="Research {topic}", backstory="Careful.", llm=llm)
    t1 = Task(description="Collect facts about {topic}.", expected_output="Facts.", agent=a)
    t2 = Task(description="Summarise the facts about {topic}.", expected_output="A summary.", agent=a)
    return Crew(agents=[a], tasks=[t1, t2])


async def check(make_llm):
    llm_a, llm_b = make_llm(), make_llm()
    await asyncio.gather(
        build(llm_a).akickoff(inputs={"topic": "bees"}),
        build(llm_b).akickoff(inputs={"topic": "volcanoes"}),
    )
    assert all("volcanoes" not in str(c["messages"]) for c in llm_a.calls)
    assert all("bees" not in str(c["messages"]) for c in llm_b.calls)
```

Call `asyncio.run(check(StubLLM))` with the stub class from that skill.
