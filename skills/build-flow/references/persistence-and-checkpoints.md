# Persistence and Checkpoints

Where flow state is saved, how to fork or resume it, how to plug in your own store, and how to resume a crashed or paused run.

---

## 1. Two systems, two jobs

| | `@persist` | Checkpointing |
|---|---|---|
| Saves | The state model after each persisted method | A full run snapshot: state, completed methods, outputs, inputs |
| Keyed by | `state.id` | A file per checkpoint under `location/<branch>/` |
| Resume with | `kickoff(restore_from_state_id=sid)` | `kickoff(from_checkpoint=CheckpointConfig(restore_from=path))` |
| Re-runs completed methods | Yes - the flow starts again from `@start` with the restored state | No - completed methods are skipped |
| Use for | Carrying state across separate runs (counters, history, sessions) | Continuing one run after a crash - only up to the first router (section 6) |

Passing both `from_checkpoint` and `restore_from_state_id` raises `ValueError: Cannot combine ...`.

---

## 2. `@persist` storage location

```python
import os
from crewai.flow.persistence import SQLiteFlowPersistence

os.environ["CREWAI_STORAGE_DIR"] = os.path.abspath("flow-state")   # absolute path
print(SQLiteFlowPersistence().db_path)   # <cwd>/flow-state/flow_states.db
```

- The default directory is `appdirs.user_data_dir(name, "CrewAI")`, where `name` is `CREWAI_STORAGE_DIR` or the current directory's name. A relative value is an app name, not a path: on macOS it resolves under `~/Library/Application Support/`, on Linux under `~/.local/share/`. An absolute value is used as the directory itself.
- Because the default depends on the working directory's name, running the same flow from two different directories uses two different databases. Pin it with `CREWAI_STORAGE_DIR` or an explicit path.
- Explicit path per flow: `@persist(SQLiteFlowPersistence("/abs/path/flows.db"))`.

---

## 3. Fork vs resume

```python
from pydantic import BaseModel
from crewai.flow import Flow, persist, start


class C(BaseModel):
    count: int = 0
    label: str = "a"


@persist()
class P(Flow[C]):
    @start()
    def bump(self):
        self.state.count += 1
        return (self.state.count, self.state.label)


p = P()
p.kickoff()                                                 # (1, 'a')
q = P()
print(q.kickoff(inputs={"label": "b"}, restore_from_state_id=p.state.id))   # (2, 'b')
print(q.state.id != p.state.id)                             # True
```

- `restore_from_state_id` is a **fork**: it loads the latest snapshot for that id, assigns a fresh `state.id`, then applies `inputs` on top.
- `inputs={"id": sid}` is the deprecated **resume**: it loads the snapshot and keeps writing under the same id. It still works in 1.15.22 and 1.15.23 and emits no warning, which is why old code keeps using it. Per the docs, on a hosted deployment reusing an id merges executions (status, traces and list rows); the HTTP kickoff body uses a top-level `restoreFromStateId` next to `inputs` instead. On CrewAI AMP (2026-10-01) `inputs.id` restored the state and kept the old `state.id`, while `restoreFromStateId` restored it under a new id equal to the new `kickoff_id`.
- Both are silent when nothing is found: an unknown id logs a message and runs from defaults, and a class without `@persist` ignores `restore_from_state_id`.

---

## 4. Method-level `@persist`

```python
from pydantic import BaseModel
from crewai.flow import Flow, listen, persist, start


class S(BaseModel):
    stage: str = ""


class Pipeline(Flow[S]):
    @start()
    def fetch(self):
        self.state.stage = "fetched"

    @persist()                 # only this method's completion is saved
    @listen(fetch)
    def transform(self):
        self.state.stage = "transformed"

    @listen(transform)
    def notify(self):
        self.state.stage = "notified"


Pipeline().kickoff()   # one row saved, with stage == "transformed"
```

Class-level `@persist()` saves after every method, so a restore picks up the state as of the last method that finished.

---

## 5. Your own store (`FlowPersistence`)

`@persist` is a local SQLite file. When state must outlive the machine or container, back it with storage you own. Implement three methods:

```python
import json
from typing import Any

from pydantic import BaseModel, PrivateAttr
from crewai.flow import Flow, persist, start
from crewai.flow.persistence import FlowPersistence


class DictPersistence(FlowPersistence):
    """Replace the dict with your database client."""

    _rows: dict[str, str] = PrivateAttr(default_factory=dict)

    def init_db(self) -> None:
        pass   # connect / create tables here

    def save_state(self, flow_uuid: str, method_name: str,
                   state_data: dict[str, Any] | BaseModel) -> None:
        data = state_data.model_dump() if isinstance(state_data, BaseModel) else state_data
        self._rows[flow_uuid] = json.dumps(data)

    def load_state(self, flow_uuid: str) -> dict[str, Any] | None:
        raw = self._rows.get(flow_uuid)
        return json.loads(raw) if raw else None


store = DictPersistence()


class C(BaseModel):
    count: int = 0


@persist(store)
class Counter(Flow[C]):
    @start()
    def bump(self):
        self.state.count += 1
        return self.state.count


a = Counter()
a.kickoff()
print(Counter().kickoff(restore_from_state_id=a.state.id))   # 2
```

`crewai.flow.persistence.factory.set_flow_persistence_factory(fn)` sets the process-wide default used by every bare `@persist()`.

---

## 6. Checkpoint, crash, resume

```python
import glob
import os
from pydantic import BaseModel
from crewai import CheckpointConfig
from crewai.flow import Flow, listen, start


class S(BaseModel):
    fail: bool = True
    loaded: int = 0


class Etl(Flow[S]):
    @start()
    def extract(self):
        return 3

    @listen(extract)
    def load(self, rows):
        if self.state.fail:
            raise RuntimeError("database down")
        self.state.loaded = rows
        return f"loaded {rows}"


cfg = CheckpointConfig(location="./.checkpoints", on_events=["method_execution_finished"])
try:
    Etl(checkpoint=cfg).kickoff()
except RuntimeError:
    pass

# newest by mtime: file names carry a one-second timestamp plus a random id, so sorting names
# can pick an older file when several methods finish in the same second
latest = max(glob.glob("./.checkpoints/**/*.json", recursive=True), key=os.path.getmtime)

# kickoff(from_checkpoint=...) replays with the saved state, so it fails again here.
# To fix state first, restore, edit, then kick off:
flow = Etl.from_checkpoint(CheckpointConfig(restore_from=latest))
flow.state.fail = False
print(flow.kickoff())   # "loaded 3" - extract() is skipped
```

- Flows need `on_events=["method_execution_finished"]`; the default `["task_completed"]` wrote nothing for a flow, even when a method ran a crew.
- This example has no router. Resume does not continue past a router: from a checkpoint taken after a `@router` (or a `@human_feedback` method with `emit`) finished, `kickoff()` runs nothing and returns the label (or `None`) with no error, so a failure downstream of a router cannot be resumed from the latest checkpoint. Reproduced on 1.15.22 and 1.15.23 with `a -> @router r -> left -> finish` (finish raising): resuming the checkpoint after `a` ran `left` and `finish`; the checkpoints after `r` and after `left` returned `'go_left'` and `None` and never ran `finish`.
- `max_checkpoints=N` prunes old files. `provider=SqliteProvider()` (from `crewai.state`) stores them in one database file instead.
- Inspect from the shell: `crewai checkpoint list ./.checkpoints`, `crewai checkpoint info <file>`.

---

## 7. Paused human feedback (no console)

A provider that raises `HumanFeedbackPending` pauses the flow; `kickoff()` returns the pending object and the state is saved. Resume later, in any process, with the same persistence.

```python
from crewai.flow import (Flow, HumanFeedbackPending, PendingFeedbackContext,
                         human_feedback, listen, start)
from crewai.flow.persistence import SQLiteFlowPersistence


class NotifyReviewer:
    def request_feedback(self, context: PendingFeedbackContext, flow) -> str:
        # send context.flow_id and context.method_output to your UI or ticketing system
        raise HumanFeedbackPending(context=context)


class Review(Flow):
    @start()
    @human_feedback(message="Approve?", emit=["rejected", "approved"],
                    llm="openai/gpt-4o-mini", default_outcome="rejected",
                    provider=NotifyReviewer())
    def write(self):
        return "draft v1"

    @listen("approved")
    def publish(self, result):
        return "published"

    @listen("rejected")
    def drop(self, result):
        return "dropped"


store = SQLiteFlowPersistence("./hitl.db")
pending = Review(persistence=store).kickoff()
assert isinstance(pending, HumanFeedbackPending)
flow_id = pending.context.flow_id

# later, e.g. in a webhook handler
print(Review.from_pending(flow_id, SQLiteFlowPersistence("./hitl.db")).resume(""))   # "dropped"
```

- Give `llm=` a model string here. The paused context stores the LLM as a model string and rebuilds it on resume, so a custom `BaseLLM` instance cannot be rebuilt (`ImportError: Unable to initialize LLM with model ...`).
- `resume("")` (empty feedback) takes `default_outcome` without calling the LLM.
