# Example tests

Complete pytest files for the patterns in SKILL.md. They assume `tests/conftest.py` and `tests/stub_llm.py` from SKILL.md section 3. The crew examples use the scaffold from `crewai create crew acme_research --classic`, and the flow example uses the scaffold from `crewai create flow acme_flow`.

---

## 1. Guardrail truth table and retry exhaustion

This file reuses `Brief`, `max_three_bullets` and `brief_crew` from `tests/test_guardrails.py` in SKILL.md section 6. pytest puts `tests/` on `sys.path`, so the import works.

```python
# tests/test_guardrails_more.py
import pytest

from crewai.tasks.task_output import TaskOutput
from stub_llm import StubLLM
from test_guardrails import brief_crew, max_three_bullets


def out(raw):
    return TaskOutput(description="d", agent="Writer", raw=raw)


@pytest.mark.parametrize("raw,accepted", [
    ('{"title": "t", "bullets": ["a"]}', True),
    ('{"title": "t", "bullets": []}', True),
    ('{"title": "t", "bullets": ["a", "b", "c", "d"]}', False),
    ("not json", False),
])
def test_truth_table(raw, accepted):
    assert max_three_bullets(out(raw))[0] is accepted


def test_rejection_message_is_specific():
    assert max_three_bullets(out('{"title": "t", "bullets": ["a", "b", "c", "d"]}')) == (
        False, "Use at most 3 bullets, you used 4.")


def test_gives_up_after_max_retries():
    llm = StubLLM(default_response='{"title": "T", "bullets": ["a", "b", "c", "d"]}')
    with pytest.raises(Exception, match="Task failed guardrail validation after 2 retries"):
        brief_crew(llm).kickoff()
    assert len(llm.calls) == 3  # first attempt + guardrail_max_retries=2
```

---

## 2. A flow whose step builds a crew

The `crewai create flow` scaffold builds `ContentCrew().crew()` inside a flow method, so there is no parameter to inject an LLM. Patch the crew class so every crew it builds gets the stub.

```python
# tests/test_flow.py
from pathlib import Path

from acme_flow.crews.content_crew.content_crew import ContentCrew
from acme_flow.main import ContentFlow
from stub_llm import StubLLM


def test_content_flow_with_stubbed_crew(monkeypatch):
    stub = StubLLM(responses=["outline", "draft", "final post"])
    original = ContentCrew.crew

    def crew_with_stub(self):
        crew = original(self)
        for agent in crew.agents:
            agent.llm = stub
        return crew

    monkeypatch.setattr(ContentCrew, "crew", crew_with_stub)

    flow = ContentFlow()
    flow.kickoff(inputs={"crewai_trigger_payload": {"topic": "bees"}})

    assert flow.state.topic == "bees"                          # payload reached the @start method
    assert flow.state.final_post == "final post"
    assert Path("output/post.md").read_text() == "final post"  # written into the tmp cwd
    assert len(stub.calls) == 3                                # planner, writer, editor
```

If you own the flow code, add a seam instead. `Flow` is a pydantic model, so declare `llm: Any = None` on the flow class, pass it to the crew it builds, and construct `MyFlow(llm=stub)` in tests.

---

## 3. Event listeners

A debug listener for real runs. Put it in its own module and import it from `main.py`, so it is instantiated once:

```python
# debug_listener.py
from crewai.events import (BaseEventListener, LLMCallCompletedEvent, TaskFailedEvent,
                           ToolUsageFinishedEvent)


class DebugListener(BaseEventListener):
    def setup_listeners(self, bus):
        @bus.on(ToolUsageFinishedEvent)
        def on_tool(source, event):
            print(f"[tool] {event.tool_name} -> {str(event.output)[:200]}")

        @bus.on(LLMCallCompletedEvent)
        def on_llm(source, event):
            print(f"[llm] {str(event.response)[:200]}")

        @bus.on(TaskFailedEvent)
        def on_task_failed(source, event):
            print(f"[task failed] {event.error}")


debug_listener = DebugListener()  # instantiating registers the handlers
```

A recorder that tests what was emitted:

```python
# tests/test_events.py
from crewai import Agent, Crew, Task
from crewai.events import (BaseEventListener, LLMCallCompletedEvent, TaskCompletedEvent,
                           crewai_event_bus)
from stub_llm import StubLLM


class Recorder(BaseEventListener):
    def __init__(self):
        self.seen = []
        super().__init__()  # calls setup_listeners(crewai_event_bus)

    def setup_listeners(self, bus):
        @bus.on(LLMCallCompletedEvent)
        def on_llm(source, event):
            self.seen.append(("llm", event.response))

        @bus.on(TaskCompletedEvent)
        def on_task(source, event):
            self.seen.append(("task", event.output.raw))


def run(llm):
    agent = Agent(role="Writer", goal="Write", backstory="Concise.", llm=llm)
    task = Task(description="Say hello", expected_output="A greeting", agent=agent)
    with crewai_event_bus.scoped_handlers():  # handlers are removed after the block
        recorder = Recorder()
        Crew(agents=[agent], tasks=[task]).kickoff()
        crewai_event_bus.flush()  # handlers run on worker threads; wait for them
    return recorder.seen


def test_listener_sees_llm_and_task_events():
    assert run(StubLLM(responses=["hello"])) == [("llm", "hello"), ("task", "hello")]


def test_custom_llm_that_does_not_emit_is_invisible():
    assert run(StubLLM(responses=["hello"], emit_events=False)) == [("task", "hello")]
```

The second test is the custom-LLM trap. Turn off the stub's event emission and the listener sees the task but not one LLM call. The tracing listener subscribes to the same events, so traces miss those calls too.

---

## 4. Offline check of the `crewai test` wiring

This checks only that `Crew.test` runs and prints scores. The judge is a stub, so the score means nothing.

```python
# tests/test_crew_eval.py
from acme_research.crew import AcmeResearch
from stub_llm import StubLLM


def test_crew_test_entry_point_runs(capsys):
    crew = AcmeResearch().crew()
    worker = StubLLM(default_response="ok")
    for agent in crew.agents:
        agent.llm = worker
    judge = StubLLM(default_response='{"quality": 8.5}')

    crew.test(n_iterations=2, eval_llm=judge, inputs={"topic": "bees", "current_year": "2026"})

    assert len(worker.calls) == 4  # 2 tasks x 2 iterations
    assert len(judge.calls) == 4   # one score per task per iteration
    assert "8.5" in capsys.readouterr().out
```

crewai 1.15.22-1.15.23 logs `[CrewAIEventsBus] Sync handler error in on_crew_test_result` once per score during `Crew.test`. It does not fail the run.
