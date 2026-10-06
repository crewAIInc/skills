# Routing Patterns

Tested wiring patterns for `@router`, `or_` and `and_`, plus one complete flow that combines them with structured state and `@persist`.

---

## 1. Revision loop (router + `or_`)

`or_` fires once per kickoff, but a router emitting one of its labels again re-arms it. That is what lets a loop run more than once.

```python
from pydantic import BaseModel
from crewai.flow import Flow, listen, or_, router, start


class DraftState(BaseModel):
    reviews: int = 0
    log: list[str] = []


class RevisionFlow(Flow[DraftState]):
    @start()
    def write_draft(self):
        self.state.log.append("write")

    @listen(or_(write_draft, "needs_revision"))
    def review(self):
        self.state.reviews += 1
        self.state.log.append(f"review{self.state.reviews}")

    @router(review)
    def decide(self):
        # Always bound a loop: a counter in state is the simplest guard.
        return "approved" if self.state.reviews >= 3 else "needs_revision"

    @listen("approved")
    def publish(self):
        self.state.log.append("publish")
        return "published"


flow = RevisionFlow()
print(flow.kickoff(), flow.state.log)
# published ['write', 'review1', 'review2', 'review3', 'publish']
```

- The label `needs_revision` is not the name of any method. If `decide` returned `"review"` instead, the flow would loop until `RecursionError` (100 calls of one method).
- Keep a hard cap in state. Nothing else stops a loop whose exit condition never becomes true.

---

## 2. Nested conditions

```python
from crewai.flow import Flow, and_, listen, or_, start

seen = []


class Nested(Flow):
    @start()
    def a(self):
        return "a"

    @start()
    def b(self):
        return "b"

    @start()
    def c(self):
        return "c"

    @listen(and_(a, or_(b, c)))       # a, plus either b or c
    def joined(self, value):
        seen.append("joined")


Nested().kickoff()
print(seen)   # ['joined'] - once
```

---

## 3. Chained routers

A router can listen to another router's label. Give each router its own label set.

```python
from typing import Literal
from pydantic import BaseModel
from crewai.flow import Flow, listen, router, start


class OrderState(BaseModel):
    amount: int = 0
    country: str = ""
    path: list[str] = []


class OrderFlow(Flow[OrderState]):
    @start()
    def receive(self):
        self.state.path.append("receive")

    @router(receive)
    def check_amount(self) -> Literal["large_order", "small_order"]:
        return "large_order" if self.state.amount > 1000 else "small_order"

    @router("large_order")
    def check_country(self) -> Literal["domestic_review", "export_review"]:
        return "domestic_review" if self.state.country == "US" else "export_review"

    @listen("small_order")
    def auto_approve(self):
        self.state.path.append("auto_approve")

    @listen("domestic_review")
    def domestic(self):
        self.state.path.append("domestic")

    @listen("export_review")
    def export(self):
        self.state.path.append("export")


f = OrderFlow()
f.kickoff(inputs={"amount": 5000, "country": "DE"})
print(f.state.path)   # ['receive', 'export']
```

---

## 4. Complete sample: router + `or_` + `@persist` + structured state + crew

This is the shape of a typical production flow. Agents use a model string; set the matching provider key (`OPENAI_API_KEY=<your-key>`) to run it for real.

```python
from typing import Literal

from pydantic import BaseModel

from crewai import Agent, Crew, Task
from crewai.flow import Flow, listen, or_, persist, router, start


class LeadState(BaseModel):
    company: str = ""
    employees: int = 0
    summary: str = ""
    tier: str = ""
    owner: str = ""
    runs: int = 0


def research_crew() -> Crew:
    researcher = Agent(role="Lead Researcher", goal="Profile {company}",
                       backstory="You research B2B leads.", llm="openai/gpt-4o-mini")
    task = Task(description="Profile {company}, which has {employees} employees.",
                expected_output="Three bullet points.", agent=researcher)
    return Crew(agents=[researcher], tasks=[task])


@persist()
class LeadFlow(Flow[LeadState]):
    @start()
    def enrich(self):
        self.state.runs += 1
        out = research_crew().kickoff(
            inputs={"company": self.state.company, "employees": self.state.employees})
        self.state.summary = out.raw

    @router(enrich)
    def classify(self) -> Literal["enterprise", "smb"]:
        return "enterprise" if self.state.employees >= 1000 else "smb"

    @listen("enterprise")
    def assign_account_exec(self):
        self.state.tier, self.state.owner = "enterprise", "account-exec"

    @listen("smb")
    def assign_nurture(self):
        self.state.tier, self.state.owner = "smb", "nurture"

    @listen(or_(assign_account_exec, assign_nurture))
    def record(self):
        return {"company": self.state.company, "tier": self.state.tier,
                "owner": self.state.owner, "runs": self.state.runs}


first = LeadFlow()
print(first.kickoff(inputs={"company": "acme", "employees": 5000}))
# {'company': 'acme', 'tier': 'enterprise', 'owner': 'account-exec', 'runs': 1}

again = LeadFlow()
print(again.kickoff(restore_from_state_id=first.state.id))   # runs == 2, new state.id
```

In a scaffolded project, put this in `src/<pkg>/main.py` and keep the entry point returning `None`:

```python
def kickoff():
    LeadFlow().kickoff(inputs={"company": "acme", "employees": 5000})


def plot():
    LeadFlow().plot("lead_flow.html", show=False)
```
