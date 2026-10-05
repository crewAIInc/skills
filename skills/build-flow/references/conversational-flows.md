# Conversational Flows

Multi-turn chat on a Flow: one `handle_turn()` call per user message, with history kept in `ConversationState`.

Official guide: https://docs.crewai.com/en/guides/flows/conversational-flows

---

## 1. Imports

| Use | Not |
|---|---|
| `from crewai.flow import ConversationConfig, ConversationState, RouterConfig` | `from crewai.experimental.conversational import ...` - a deprecated alias that resolves to the same module (no warning) |
| `flow.handle_turn(message, session_id=...)` | `flow.kickoff(user_message=..., session_id=...)` - `TypeError: Flow.kickoff() got an unexpected keyword argument 'user_message'` |
| `flow.stream_turn(message, session_id=...)` for streamed turns | `ChatSession` - there is no such class in `crewai.flow` |

---

## 2. Minimal flow with deterministic routing

```python
from crewai.flow import ConversationConfig, ConversationState, Flow, listen


@ConversationConfig(system_prompt="")        # the decorator also marks the flow conversational
class SupportFlow(Flow[ConversationState]):

    def route_turn(self, context):
        text = (self.state.current_user_message or "").lower()
        if "order" in text:
            return "ORDER"
        return "end"                         # built-in route that ends the conversation

    @listen("ORDER")
    def handle_order(self) -> str:
        """Order status questions."""        # first docstring line describes the route
        return "Your order is on the way."   # a returned string becomes the assistant reply


flow = SupportFlow()
try:
    print(flow.handle_turn("Where is my order?", session_id="support-123"))
    # Your order is on the way.
    print([m.role for m in flow.state.messages])      # ['user', 'assistant']
    print(flow.handle_turn("bye", session_id="support-123"))
    # Conversation ended.
finally:
    flow.finalize_session_traces()
```

- `session_id` becomes `state.id`. With `@persist`, each turn hydrates the saved conversation for that id.
- `handle_turn()` appends the user message before the graph runs; do not append it again in a handler.
- Route labels follow the same rule as any router: they must not equal a handler's method name (`ORDER` / `handle_order`).
- Built-in routes: `converse` (LLM reply using history; needs `llm=` on `ConversationConfig`), `end`.
- Leave `route_turn` out and set `ConversationConfig(llm=...)` to have an LLM pick the route from your `@listen` labels and their docstrings.

`crewai run` detects a conversational flow in the `kickoff` script's module and opens the terminal chat UI instead of running the flow once.
