"""Deterministic, offline stub LLM for crewai 1.15.x.

Drop this file into your project's ``tests/`` directory. It lets Agent, Crew
and Flow code run end to end with no network and no API key, so tests are
fast and reproducible.

    from stub_llm import StubLLM
    from crewai import Agent, Task, Crew

    llm = StubLLM(responses=["first task answer", "second task answer"])
    agent = Agent(role="Writer", goal="Write", backstory="Writes things", llm=llm)
    t1 = Task(description="Draft", expected_output="A draft", agent=agent)
    t2 = Task(description="Polish", expected_output="Final text", agent=agent)
    out = Crew(agents=[agent], tasks=[t1, t2]).kickoff()
    assert out.raw == "second task answer"
    assert len(llm.calls) == 2

Response sources, in priority order, for each call:
  1. ``responses``: a queue consumed one item per LLM call. Each item is a
     str, a dict / list (serialized to JSON - use this for output_pydantic,
     output_json and response_model), a pydantic BaseModel (serialized to
     JSON), or a callable ``f(messages, response_model) -> str | dict | BaseModel``.
  2. ``responder``: a callable used once the queue is empty (or always, when
     no queue is given).
  3. ``default_response``: returned when both are exhausted. If you did NOT
     set ``default_response`` and the caller passed a ``response_model``, a
     JSON object built from that model's defaults / placeholders is returned.

Driving tools: ``supports_function_calling()`` returns False, so crewai uses
the ReAct text loop for tool-using agents. Queue a tool call
(``tool_call()`` below builds the string) and then the final answer:

    StubLLM(responses=[tool_call("my_tool", {"x": 1}), "final answer"])

The tool's real ``_run`` executes between the two calls.

Every call is recorded in ``llm.calls`` as a dict with keys ``messages``,
``response_model``, ``tools`` and ``response``, so tests can assert on the
prompts crewai built. ``prompt_text(call)`` flattens one call's messages
into a single string for substring assertions.

When crewai passes a ``response_model`` (a task with output_pydantic /
output_json / response_model on an agent WITHOUT tools) and the response
validates against it, ``call`` returns the model instance, as the native
providers do. Set ``native_structured_output=False`` to always return text.

The stub emits LLMCallStartedEvent / LLMCallCompletedEvent like the native
providers do, so event listeners and traces see its calls. Set
``emit_events=False`` to turn that off.

Base class import: ``from crewai import BaseLLM``. The only abstract method
is ``call``.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

from crewai import BaseLLM
from crewai.llms.base_llm import llm_call_context


def tool_call(tool_name: str, args: dict[str, Any] | None = None,
              thought: str = "I should use a tool.") -> str:
    """Return a ReAct-format response that makes the agent run ``tool_name``."""
    return (
        f"Thought: {thought}\n"
        f"Action: {tool_name}\n"
        f"Action Input: {json.dumps(args or {})}"
    )


def prompt_text(call: dict[str, Any]) -> str:
    """Flatten one recorded call's messages into a single string."""
    messages = call["messages"]
    if isinstance(messages, str):
        return messages
    return "\n".join(str(m.get("content", "")) for m in messages)


def _placeholder_for(annotation: Any) -> Any:
    origin = getattr(annotation, "__origin__", None)
    if annotation is str:
        return "stub"
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if annotation is bool:
        return False
    if origin in (list, tuple, set):
        return []
    if origin is dict or annotation is dict:
        return {}
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _skeleton(annotation)
    return None


def _skeleton(model: type[BaseModel]) -> dict[str, Any]:
    """Build a minimal valid-looking JSON object for a pydantic model."""
    data: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        if not field.is_required():
            default = field.get_default(call_default_factory=True)
            data[name] = default.model_dump() if isinstance(default, BaseModel) else default
        else:
            data[name] = _placeholder_for(field.annotation)
    return data


class StubLLM(BaseLLM):
    """Offline deterministic LLM. See the module docstring for usage."""

    model: str = "stub/deterministic"
    provider: str = "stub"
    responses: list[Any] = Field(default_factory=list)
    responder: Callable[..., Any] | None = None
    default_response: str = "Stub final answer."
    prompt_tokens_per_call: int = 10
    completion_tokens_per_call: int = 5
    emit_events: bool = True
    native_structured_output: bool = True

    # Mutable containers on purpose: Crew.copy() (used by Crew.test and
    # kickoff_for_each) shallow-copies each agent's LLM, and the copies must
    # share one queue cursor and one call log with the original.
    _cursor: list[int] = PrivateAttr(default_factory=lambda: [0])
    _calls: list[dict[str, Any]] = PrivateAttr(default_factory=list)

    def __init__(self, **data: Any) -> None:
        # BaseLLM's validator rejects a missing or empty model, so supply one.
        data.setdefault("model", "stub/deterministic")
        data.setdefault("provider", "stub")
        super().__init__(**data)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._calls

    def reset(self) -> None:
        self._cursor[0] = 0
        self._calls.clear()

    @staticmethod
    def _to_text(value: Any) -> str:
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    def _next(self, messages: Any, response_model: type[BaseModel] | None) -> str:
        if self._cursor[0] < len(self.responses):
            item = self.responses[self._cursor[0]]
            self._cursor[0] += 1
            if callable(item) and not isinstance(item, type):
                item = item(messages, response_model)
            return self._to_text(item)
        if self.responder is not None:
            return self._to_text(self.responder(messages, response_model))
        if response_model is not None and "default_response" not in self.model_fields_set:
            return json.dumps(_skeleton(response_model))
        return self.default_response

    def call(
        self,
        messages: Any,
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any = None,
        from_agent: Any = None,
        response_model: type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> Any:
        # llm_call_context() gives the started/completed events a shared
        # call_id, the same way the native providers do.
        with llm_call_context():
            return self._call(
                messages, tools, callbacks, available_functions,
                from_task, from_agent, response_model,
            )

    def _call(
        self,
        messages: Any,
        tools: list[dict[str, Any]] | None,
        callbacks: list[Any] | None,
        available_functions: dict[str, Any] | None,
        from_task: Any,
        from_agent: Any,
        response_model: type[BaseModel] | None,
    ) -> Any:
        # Custom BaseLLM subclasses must emit LLM events themselves; without
        # this, event listeners and traces never see the call.
        if self.emit_events:
            self._emit_call_started_event(
                messages=messages,
                tools=tools,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
            )
        text = self._next(messages, response_model)
        self._calls.append(
            {
                # crewai keeps appending to the same list object, so snapshot it.
                "messages": copy.deepcopy(messages),
                "response_model": response_model,
                "tools": tools,
                "response": text,
            }
        )
        usage = {
            "prompt_tokens": self.prompt_tokens_per_call,
            "completion_tokens": self.completion_tokens_per_call,
            "total_tokens": self.prompt_tokens_per_call + self.completion_tokens_per_call,
        }
        self._track_token_usage_internal(usage)
        if self.emit_events:
            from crewai.events.types.llm_events import LLMCallType

            self._emit_call_completed_event(
                response=text,
                call_type=LLMCallType.LLM_CALL,
                from_task=from_task,
                from_agent=from_agent,
                messages=messages,
                usage=usage,
            )
        if self.native_structured_output and response_model is not None:
            # Native providers hand back a validated model instance when crewai
            # passes response_model; mirror that so tests see the same shapes.
            try:
                return response_model.model_validate_json(text)
            except ValueError:
                pass
        return text

    async def acall(self, *args: Any, **kwargs: Any) -> Any:
        return self.call(*args, **kwargs)

    def supports_function_calling(self) -> bool:
        # False keeps tool-using agents on the ReAct text loop, which is what
        # tool_call() drives. crewai's output converter also calls this.
        return False

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 128_000
