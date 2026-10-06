# Conversational Flows Reference

Guidance for building multi-turn chat applications with CrewAI Flows.

Official docs: <https://docs.crewai.com/en/guides/flows/conversational-flows>

Verified against crewai 1.15.23 on 2026-10-01; the routing, `converse`, `stream_turn()` and history behaviour below were run with `anthropic/claude-haiku-4-5`.

---

## Mental Model

Conversational apps treat each user line as a new Flow run with the same session id.

| Concept | Implementation |
|---|---|
| Session id | `handle_turn(..., session_id=...)` maps to `kickoff(inputs={"id": ...})` and `state.id` |
| User line | `handle_turn(message)` appends to `state.messages` before the graph runs |
| Turn complete | `conversation_turn_completed` event; with trace deferral (the default), `FlowFinished` waits for `finalize_session_traces()` |
| Full-session trace | `ConversationConfig(defer_trace_finalization=True)` plus `finalize_session_traces()` |

Do not call `Flow.kickoff(user_message=..., session_id=...)` - it raises `TypeError: Flow.kickoff() got an unexpected keyword argument 'user_message'`. `kickoff()` accepts normal Flow execution inputs; `handle_turn()` is the chat wrapper. `handle_turn()`, `stream_turn()` and `chat()` raise `ValueError` on a Flow that is not conversational.

---

## API Selection

| API | Use for |
|---|---|
| `flow.handle_turn(message, session_id=...)` | One chat turn from REST, WebSocket, tests, workers, or custom UI |
| `flow.chat()` | Local terminal REPL for a conversational Flow |
| `flow.kickoff(inputs={...})` | Advanced raw Flow execution without turn hydration |
| `ask()` | Blocking prompt inside one step, such as a wizard clarification |
| `@human_feedback` | Approving or rejecting a step output, not collecting the next chat line |
| `flow.stream_turn(message, session_id=...)` | One turn as ordered stream frames (routing, LLM chunks, tool activity, messages) for SSE/WebSocket bridges |

---

## Minimal Flow

```python
from crewai import Flow
from crewai.flow import ConversationConfig, ConversationState, listen
# crewai.experimental.conversational is a deprecated alias of the same module


@ConversationConfig(defer_trace_finalization=True)   # True is the default; the decorator also sets conversational = True
class SupportFlow(Flow[ConversationState]):

    def route_turn(self, context):
        message = (self.state.current_user_message or "").lower()
        if "order" in message:
            return "ORDER"
        if "bye" in message or "goodbye" in message:
            return "end"
        return "converse"

    @listen("ORDER")
    def handle_order(self) -> str:
        """Order status, fulfillment, and return questions."""
        reply = "Your order is on the way."
        self.append_assistant_message(reply)
        return reply
```

```python
flow = SupportFlow()

try:
    flow.handle_turn("Where is my order?", session_id="support-123")   # -> "Your order is on the way."
    flow.handle_turn("What about returns?", session_id="support-123")  # -> converse route
finally:
    flow.finalize_session_traces()
```

This config has no `llm`, so the built-in `converse` route answers "I can continue the conversation once an LLM is configured." Add `llm=` to `ConversationConfig` for real chat replies.

### With an LLM for `converse`

```python
from uuid import uuid4

from crewai import Flow
from crewai.flow import ConversationConfig, ConversationState, listen


@ConversationConfig(llm="openai/gpt-4o-mini")   # used by the built-in `converse` route
class SupportFlow(Flow[ConversationState]):

    def route_turn(self, context):
        message = (self.state.current_user_message or "").lower()
        if "docs" in message or "crewai" in message:
            return "CREWAI_DOCS"
        return "converse"

    @listen("CREWAI_DOCS")
    def handle_docs(self):
        """Look up CrewAI documentation for framework/API questions."""
        reply = "I would query the CrewAI docs here."
        self.append_assistant_message(reply)
        return reply


flow = SupportFlow()
session_id = str(uuid4())

try:
    flow.handle_turn("Hi! My name is Ada. What can you do?", session_id=session_id)  # -> converse (LLM reply)
    flow.handle_turn("Check the CrewAI docs for flows.", session_id=session_id)      # -> CREWAI_DOCS
    flow.handle_turn("What is my name?", session_id=session_id)                      # -> converse: "Your name is Ada."
finally:
    flow.finalize_session_traces()
```

Live run with `anthropic/claude-haiku-4-5` as the `llm`: routes were `converse`, `CREWAI_DOCS`, `converse`, the last reply was "Your name is Ada.", `state.messages` alternated user/assistant with no duplicates, and `state.id` equalled the session id.

For a local REPL:

```python
def kickoff() -> None:
    SupportFlow().chat()
```

`chat()` wraps `handle_turn()`, exits on commands like `exit` / `quit`, skips blank input by default, prints replies, and finalizes deferred traces. It takes `input_fn=` / `output_fn=` for tests. In a scaffolded project, `crewai run` opens a terminal chat UI for a conversational flow (it needs a TTY; headless, drive it from Python with `handle_turn()`).

---

## Turn Lifecycle

Each `handle_turn()` call:

1. Stores the pending user message and resolves the session id.
2. Resets per-turn execution tracking so the graph can run again on the same Flow instance.
3. Calls `kickoff(inputs={"id": session_id})`.
4. Restores persisted state for that id when `@persist` is configured.
5. Appends the user message to `state.messages` and sets fields like `current_user_message` / `last_user_message`.
6. Optionally classifies intent when `intents` or `default_intents` plus an intent LLM are configured.
7. Runs the built-in `route_conversation` router (which calls your `route_turn()`, then the LLM router or `converse`) -> the selected `@listen` handler.
8. Skips per-turn trace finalization when trace deferral is enabled.

A string a handler returns becomes the assistant message; calling `append_assistant_message(reply)` and returning the same reply records it once, not twice. The user line is already stored by `handle_turn()`; do not append it again in handlers.

---

## ConversationConfig

Attach chat defaults as a class decorator:

```python
@ConversationConfig(defer_trace_finalization=True)
class SupportFlow(Flow[ConversationState]):
    conversational = True
```

Common fields:

| Field | Purpose |
|---|---|
| `system_prompt` | System message used by the built-in `converse_turn`; pass `""` to opt out |
| `llm` | Conversation LLM for `converse_turn` and router fallback |
| `router` | `RouterConfig` for LLM-driven routing |
| `answer_from_history_llm` / `answer_from_history_prompt` | Deprecated (`DeprecationWarning`); the `converse` route already answers from history |
| `intent_llm` / `default_intents` | Legacy/simple pre-classification before routing |
| `visible_agent_outputs` | Promote selected `append_agent_result()` outputs to public assistant messages |
| `defer_trace_finalization` | Keep one trace batch open across turns; defaults to `True` |

---

## Routing

Use programmatic `route_turn()` for deterministic routing:

```python
def route_turn(self, context):
    text = (self.state.current_user_message or "").lower()
    if "docs" in text:
        return "CREWAI_DOCS"
    return "converse"
```

For LLM-driven routing, leave `route_turn()` out and set `@ConversationConfig(llm=...)`: when the flow has custom `@listen` routes, the router auto-enables with default settings (verified live: "Where is my package?" -> `ORDER`, "I was charged twice" -> `BILLING`, "Thanks, goodbye!" -> `end`). Pass an explicit `RouterConfig` only to change the prompt, descriptions, labels, or default/fallback intent:

```python
from typing import Literal
from pydantic import BaseModel
from crewai import LLM
from crewai.flow import RouterConfig


class RouteChoice(BaseModel):
    intent: Literal["CREWAI_DOCS", "RESEARCH", "converse"]


router_llm = LLM(model="openai/gpt-4o-mini")


@ConversationConfig(
    router=RouterConfig(
        response_format=RouteChoice,
        llm=router_llm,
        default_intent="converse",
        fallback_intent="converse",
    )
)
class SupportFlow(Flow[ConversationState]):
    conversational = True
```

The route catalog is auto-built. For each route, the router description comes from:

1. `RouterConfig.route_descriptions[label]`
2. Built-in route descriptions for `converse` and `end`
3. The first non-empty line of the route handler docstring
4. Empty description

Router errors (a failed LLM call, an unknown label) fall back to `fallback_intent`, then `default_intent` - silently. Adding a route should be as small as `@listen("ROUTE")` plus a one-line docstring. Keep `RouterConfig.prompt` for domain framing, policy, persona, and voice; do not duplicate the route list there.

Built-in routes:

| Route | Purpose |
|---|---|
| `converse` | Default chat handler using the configured conversation LLM and message history |
| `end` | Marks the conversation ended and emits a terminator reply |
| `answer_from_history` | Deprecated internal route, used only with `answer_from_history_llm` |

---

## Agents Inside Conversational Routes

For tool-backed work, call `Agent.kickoff()` or a crew inside a route handler.

```python
@listen("RESEARCH")
def handle_research(self) -> str:
    """Fresh research, current lookups, and source-backed synthesis."""
    result = self.research_agent().kickoff(self.state.current_user_message)
    self.append_agent_result("research_agent", result, visibility="private")
    reply = result.raw
    self.append_assistant_message(reply)
    return reply
```

Use `append_agent_result(agent_name, result, visibility="private")` for scratch work that should not pollute canonical chat history. Use public visibility or `append_assistant_message()` for user-visible responses.

---

## Persistence and Tracing

With `defer_trace_finalization=True`, the session gets one trace batch:

- `flow_started` emits on the first turn.
- Each `handle_turn()` appends events to the same batch.
- `flow_finished` emits once in `finalize_session_traces()`.
- Nested `Agent.kickoff()` and crews append to the parent batch rather than closing it early.

When you own the loop, always finalize:

```python
flow = SupportFlow()

try:
    for message in messages:
        flow.handle_turn(message, session_id=session_id)
finally:
    flow.finalize_session_traces()
```

Persistence pattern: prefer `@persist` on a single terminal step rather than the whole Flow class. Class-level persistence saves after every method, so restore can land on a mid-run snapshot that misses later handler updates from the same turn.

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| Calling `kickoff(user_message=..., session_id=...)` | Use `handle_turn(message, session_id=...)` |
| Appending the user message inside a handler | Let `handle_turn()` append the user line |
| Handler neither returns a string nor records a reply | Return the reply string, or call `append_assistant_message(reply)` |
| Setting `stream = True` on a conversational flow | Use `flow.stream_turn(message, session_id=...)` |
| Using `@human_feedback` for follow-up chat | Use another `handle_turn()` call; `@human_feedback` approves a step output |
| Forgetting to finalize session traces | Wrap owned loops in `try/finally` and call `finalize_session_traces()` |
| Listing routes in `RouterConfig.prompt` | Let route catalog auto-build from listeners and docstrings |
