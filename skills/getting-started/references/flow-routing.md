# Flow Routing Reference

Complete patterns for `@router`, `or_()`, `and_()`, conditional starts, and branch convergence.

---

## Imports

```python
from crewai.flow.flow import Flow, start, listen, router, or_, and_
from pydantic import BaseModel
```

---

## 1. Basic Router — Conditional Branching

`@router` returns a string label. `@listen("label")` binds to that branch.

```python
class QAState(BaseModel):
    draft: str = ""
    score: int = 0

class QualityFlow(Flow[QAState]):

    @start()
    def generate(self):
        self.state.draft = "Some generated content..."

    @router(generate)
    def check_quality(self):
        # Evaluate and return a route label
        self.state.score = evaluate(self.state.draft)
        if self.state.score >= 7:
            return "approved"
        return "needs_revision"

    @listen("approved")
    def publish(self):
        print(f"Publishing with score {self.state.score}")

    @listen("needs_revision")
    def revise(self):
        print("Sending back for revision")
```

**Key rules:**
- `@router` must return a **string** — this string is the route label
- `@listen("label")` must match the exact string returned by the router
- A router can return any number of different labels
- Only the matching `@listen` fires — others are skipped

---

## 2. or_() — Fire on ANY Upstream Completion

```python
class ParallelFetchFlow(Flow):

    @start()
    def fetch_source_a(self):
        return "Data from source A"

    @start()
    def fetch_source_b(self):
        return "Data from source B"

    # Fires when EITHER source completes (whichever is first)
    @listen(or_(fetch_source_a, fetch_source_b))
    def process_first(self, result):
        print(f"Got first result: {result}")
```

**Behavior:**
- `or_()` fires as soon as **any one** of its conditions completes
- It fires **once per triggering condition** — if both complete, the listener runs twice
- To run only once regardless, track state with a flag

---

## 3. and_() — Fire When ALL Upstreams Complete

```python
class MergeFlow(Flow):

    @start()
    def research(self):
        self.state["research"] = "Research findings..."

    @start()
    def market_data(self):
        self.state["market"] = "Market data..."

    # Fires only when BOTH research AND market_data complete
    @listen(and_(research, market_data))
    def merge_results(self):
        print(f"Research: {self.state['research']}")
        print(f"Market: {self.state['market']}")
```

**Behavior:**
- `and_()` waits for **all** conditions to complete before firing
- The listener receives the return value of the **last** method to complete
- Access earlier results via `self.state`

---

## 4. Nested Conditions

`or_()` and `and_()` can be nested:

```python
# Fire when (A AND B) complete, OR when C completes
@listen(or_(and_(step_a, step_b), step_c))
def converge(self):
    ...

# Fire when (A OR B) AND C all complete
@listen(and_(or_(step_a, step_b), step_c))
def converge(self):
    ...
```

---

## 5. Revision Loop Pattern

Combine `@router` with `or_()` to create retry loops:

```python
class RevisionFlow(Flow[DocState]):

    @start()
    def write_draft(self):
        self.state.draft = generate_draft(self.state.topic)

    # Listens to initial write OR revision outcome
    @listen(or_(write_draft, "needs_revision"))
    def review(self):
        self.state.review_count += 1
        return self.state.draft

    @router(review)
    def decide(self):
        if quality_score(self.state.draft) >= 8:
            return "approved"
        if self.state.review_count >= 3:
            return "approved"  # Force approve after 3 tries
        return "needs_revision"

    @listen("needs_revision")
    def revise(self):
        self.state.draft = improve_draft(self.state.draft)

    @listen("approved")
    def publish(self):
        save(self.state.draft)
```

**Key:** `@listen(or_(write_draft, "needs_revision"))` creates the loop — `review` fires after the initial write AND after each revision.

---

## 6. Conditional Starts

`@start()` can take a condition, gating on prior method completion:

```python
class ConditionalStartFlow(Flow):

    @start()  # Unconditional — always runs
    def init(self):
        self.state["ready"] = True

    @start("init")  # Runs after init completes
    def setup(self):
        ...

    @start(and_("init", "setup"))  # Runs after both
    def begin_work(self):
        ...
```

---

## 7. Flow Persistence with @persist

For long-running flows that need to survive restarts:

```python
from crewai.flow.persistence import persist, SQLiteFlowPersistence

@persist(SQLiteFlowPersistence())  # Class-level: persists all method states
class LongRunningFlow(Flow[MyState]):

    @start()
    def step_one(self):
        self.state.data = "processed"

    @listen(step_one)
    def step_two(self):
        # If the process crashes here, restarting with the same
        # state ID resumes from after step_one
        ...
```

Method-level persistence (selective):

```python
class SelectiveFlow(Flow):

    @start()
    def fast_step(self):
        ...  # Not persisted

    @persist()  # Only this method's state is persisted
    @listen(fast_step)
    def critical_step(self):
        ...
```

---

## 8. Streaming

Enable real-time output streaming from flow execution:

```python
class StreamingFlow(Flow):
    stream = True  # Enable for entire flow

    @start()
    def generate(self):
        result = SomeCrew().crew().kickoff(inputs={...})
        return result

# Synchronous streaming
flow = StreamingFlow()
streaming = flow.kickoff()

for chunk in streaming:
    print(chunk.content, end="", flush=True)

result = streaming.result  # Final complete output

# Async streaming
async def run():
    flow = StreamingFlow()
    streaming = await flow.kickoff_async()
    async for chunk in streaming:
        print(chunk.content, end="", flush=True)
    return streaming.result
```

---

## 9. Human Feedback with @human_feedback

Pause flow for human review and route based on feedback:

```python
from crewai.flow.human_feedback import human_feedback, HumanFeedbackResult

class ApprovalFlow(Flow[ReviewState]):

    @start()
    def generate_draft(self):
        result = WriterCrew().crew().kickoff(inputs={"topic": self.state.topic})
        self.state.draft = result.raw

    @human_feedback(
        message="Review the draft and provide feedback:",
        emit=["approved", "needs_revision"],   # Possible outcomes
        llm="openai/gpt-4o-mini",              # LLM to interpret feedback into outcomes
        default_outcome="approved",            # If no feedback given
        learn=True,                            # Learn from feedback for future runs
    )
    @listen(or_("generate_draft", "needs_revision"))
    def review(self):
        return self.state.draft

    @listen("approved")
    def publish(self, result: HumanFeedbackResult):
        print(f"Approved! Reviewer said: {result.feedback}")

    @listen("needs_revision")
    def revise(self, result: HumanFeedbackResult):
        # Use feedback to improve
        self.state.draft = improve(self.state.draft, result.feedback)
```

**Parameters:**
- `message` — displayed to the human reviewer
- `emit` — list of possible outcome labels (used with `@listen("label")`)
- `llm` — interprets free-text feedback into one of the `emit` labels
- `default_outcome` — used if no feedback is provided
- `learn` — if `True`, stores feedback patterns for future reference

---

## 10. Flow Visualization

```python
flow = MyFlow()
flow.plot()              # Display in notebook / terminal
flow.plot("my_flow")     # Save as my_flow.png / my_flow.html
```

Use `plot()` to verify your routing logic before running.
