# Flow Routing Reference

Complete patterns for `@router`, `or_()`, `and_()`, conditional starts, and branch convergence.

Verified against crewai 1.15.23 on 2026-10-01 (the human-feedback loop in section 9 was run with a real LLM). The **build-flow** skill covers the same API in more depth.

---

## Imports

```python
from crewai.flow import Flow, start, listen, router, or_, and_   # crewai.flow.flow also exports these, but not persist
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
- A label must not equal the name of the method that listens for it (`@listen("publish") def publish` raises at instantiation), and should not equal any method name at all - a router returning a method's name re-triggers that branch
- A label with no listener ends the flow silently

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

    # Fires ONCE, when the first source completes
    @listen(or_(fetch_source_a, fetch_source_b))
    def process_first(self, result):
        print(f"Got first result: {result}")
```

**Behavior:**
- `or_()` fires as soon as **any one** of its conditions completes, and receives that method's return value
- It fires **once per kickoff** - when the second source completes later, the listener does not run again, so no "seen" flag is needed
- It re-arms when a router emits one of its labels again, which is what makes the revision loop in section 5 work

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

    # Listens to initial write OR the label emitted after each revision
    @listen(or_(write_draft, "revised"))
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

    @router("needs_revision")
    def revise(self):
        self.state.draft = improve_draft(self.state.draft)
        return "revised"       # review runs again only after the revision is done

    @listen("approved")
    def publish(self):
        save(self.state.draft)
```

**Key:** `@listen(or_(write_draft, "revised"))` creates the loop - `review` fires after the initial write AND after each revision. Do not have `review` listen to `"needs_revision"` directly while `revise` also listens to it: both then run on the same label in parallel, and `review` re-checks the unrevised draft (verified: every review saw `v1`).

---

## 6. Conditional Starts

`@start()` can take a condition. In crewai 1.15.23 a conditional start fires on a **router label**; a condition on another method's completion (`@start("init")`, `@start(init)`, `@start(and_("init", "setup"))`) never fired in testing - only `init` ran. Chain after methods with `@listen` instead:

```python
class ConditionalStartFlow(Flow):

    @start()  # Unconditional — always runs
    def init(self):
        self.state["ready"] = True

    @router(init)
    def gate(self):
        return "go" if self.state["ready"] else "stop"

    @start("go")  # Runs when the router emits "go"
    def setup(self):
        ...

    @listen(and_(init, setup))  # Runs after both (use @listen, not @start, for method completion)
    def begin_work(self):
        ...
```

---

## 7. Flow Persistence with @persist

For long-running flows that need to survive restarts:

```python
from crewai.flow import persist                       # or crewai.flow.persistence; NOT crewai.flow.flow
from crewai.flow.persistence import SQLiteFlowPersistence

@persist(SQLiteFlowPersistence())  # Class-level: persists all method states. Bare @persist (no parentheses) raises TypeError
class LongRunningFlow(Flow[MyState]):

    @start()
    def step_one(self):
        self.state.data = "processed"

    @listen(step_one)
    def step_two(self):
        ...

flow = LongRunningFlow()
flow.kickoff()
# Later, in a new process: hydrate from the saved state (the new run gets a fresh state.id)
LongRunningFlow().kickoff(restore_from_state_id=flow.state.id)
```

State lands in `flow_states.db` under `appdirs.user_data_dir(<CREWAI_STORAGE_DIR or current dir name>, "CrewAI")` unless you pass a path: `SQLiteFlowPersistence("/abs/path/flows.db")`. An unknown id, or `restore_from_state_id` on a flow without `@persist`, is ignored silently. For crash-resume of completed methods, see checkpointing in the **build-flow** skill.

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

Enable real-time output streaming from flow execution (`kickoff()` then returns a `StreamSession` of `StreamFrame` chunks):

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

`streaming.result` raises `RuntimeError: Streaming has not completed yet` until you have iterated every chunk. For conversational flows do not set `stream = True`; use `flow.stream_turn(...)` (see [Conversational Flows](conversational-flows.md)).

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
        emit=["needs_revision", "approved"],   # Possible outcomes; safe one first
        llm="openai/gpt-4o-mini",              # LLM to interpret feedback into outcomes
        default_outcome="needs_revision",      # If no feedback given (Enter never approves)
    )
    @listen(or_(generate_draft, "revised"))
    def review(self):
        return self.state.draft

    @listen("approved")
    def publish(self, result: HumanFeedbackResult):
        print(f"Approved! Reviewer said: {result.feedback}")

    @router("needs_revision")
    def revise(self, result: HumanFeedbackResult):
        # Use feedback to improve, then loop back to review
        self.state.draft = improve(self.state.draft, result.feedback)
        return "revised"
```

Live run with a scripted reviewer and `anthropic/claude-haiku-4-5` as the `llm`: "Too vague - add a concrete example" mapped to `needs_revision`, the draft was revised, "Perfect, approved, ship it." mapped to `approved`; `human_feedback_history` outcomes were `['needs_revision', 'approved']`.

**Parameters:**
- `message` — displayed to the human reviewer
- `emit` — list of possible outcome labels (used with `@listen("label")`)
- `llm` — interprets free-text feedback into one of the `emit` labels
- `default_outcome` - used if no feedback is provided (requires `emit`)
- `provider` - an object with `request_feedback(context, flow) -> str`; the default reads the console, so pass one for tests, UIs and deployed flows
- `learn` - if `True`, distills feedback into lessons stored in the flow's `memory` and uses them to pre-review later outputs. Flow memory uses the default OpenAI embedder unless you configure another; failures are logged, not raised
- `HumanFeedbackResult` fields: `output`, `feedback`, `outcome`, `timestamp`, `method_name`, `metadata` (there is no `feedback_text`). Also on the flow: `self.last_human_feedback`, `self.human_feedback_history`
- Feedback the LLM cannot map to a label raises `HumanFeedbackCollapseError`

---

## 10. Flow Visualization

```python
flow = MyFlow()
path = flow.plot()                                # writes crewai_flow.html and opens a browser
path = flow.plot("my_flow.html", show=False)      # CI / headless: no browser
print(path)                                       # absolute path inside a new temp directory
```

`plot()` writes interactive HTML (plus a `.js` and `.css`) into a temp directory and returns the path - nothing lands in the current directory and there is no PNG. The filename is used as given, so `plot("my_flow")` writes a file with no extension. From a scaffolded project, `crewai flow plot` runs the `plot` script. Use `plot()` to verify your routing logic before running.
