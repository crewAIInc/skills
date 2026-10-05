# Source receipts

The installed crewai 1.15.22 source behind each row in the skill. Line numbers are from 1.15.22; every row's behaviour was re-checked on 1.15.23, where many of these lines moved by a few to a hundred lines - search for the symbol rather than trusting the number. Paths are relative to the environment's `site-packages/`. After an upgrade, open the file (or run `inspect.getsourcefile(Crew.kickoff)`) and re-check the row; line numbers drift between releases.

---

## Imports

| Claim | Source |
|---|---|
| `persist` is exported from `crewai.flow`, not `crewai.flow.flow` | `crewai/flow/__init__.py:25` (import), `crewai/flow/flow.py:37` (`__all__` without `persist`) |
| `ConditionalTask` lives in `crewai.tasks.conditional_task` | `crewai/__init__.py:150` |
| `BaseEventListener` lives in `crewai.events` | `crewai/events/base_event_listener.py:8` |
| `crewai.cli` is a deprecation shim | `crewai/cli/__init__.py:1` ("Deprecated: use `crewai_cli` instead.") |
| `CodeInterpreterTool` is gone | not exported by `crewai_tools/__init__.py`; `crewai/agent/core.py:288` ("CodeInterpreterTool is no longer available") |

## Agent, Task, Crew

| Claim | Source |
|---|---|
| `Task.expected_output` is required | `crewai/task.py:153` |
| `Agent.max_iter` default 25 | `crewai/agents/agent_builder/base_agent.py:286-288` |
| `Agent.cache` default True, only permits caching | `crewai/agents/agent_builder/base_agent.py:195-199, 262` |
| `Crew.cache` default False (opt-in) | `crewai/crew.py:232-239` |
| `Crew.process` default sequential; only sequential/hierarchical | `crewai/crew.py:254`; `crewai/process.py:9-11` |
| Hierarchical needs `manager_llm` or `manager_agent` | `crewai/crew.py:730` |
| `guardrail_max_retries` default 3; `max_retries` deprecated | `crewai/task.py:279`, `:577` |
| `output_pydantic` and `output_json` are exclusive | `crewai/task.py:568` |
| `allow_code_execution` / `code_execution_mode` deprecated | `crewai/agent/core.py:285-288, 311-314, 413-419` |
| `Crew.function_calling_llm` deprecated | `crewai/crew.py:294` |

## Running and output

| Claim | Source |
|---|---|
| `kickoff` needs a dict | `crewai/crews/utils.py:282` |
| `kickoff_async` wraps sync `kickoff` in `asyncio.to_thread`; `akickoff` is native | `crewai/crew.py:1135, 1168, 1187, 1215` |
| `kickoff_for_each` | `crewai/crew.py:1099` |
| `CrewOutput` fields | `crewai/crews/crew_output.py:17-27` |
| `out["key"]` reads pydantic then json_dict | `crewai/crews/crew_output.py:77` |

## LLMs

| Claim | Source |
|---|---|
| `LLM(...)` is a factory returning a native provider class | `crewai/llm.py:398` |
| Native provider list | `crewai/llm.py:330` |
| Non-native providers need the LiteLLM extra | `crewai/llm.py:504` |
| Provider extras and their error text | `crewai/llms/providers/anthropic/completion.py:44`, `.../gemini/completion.py:31`, `.../bedrock/completion.py:47`, `.../azure/completion.py:55`; `crewai-1.15.22.dist-info/METADATA` `Provides-Extra` lines |
| Default model `gpt-4.1-mini`; env resolution order | `crewai/constants.py:354`; `crewai/utilities/llm_utils.py:104-108` |
| Provider `call` takes `response_model`, not `response_format` | `crewai/llms/providers/openai/completion.py:581` |
| `BaseLLM.call` is the one abstract method and receives `from_task`, `from_agent`, `response_model` | `crewai/llms/base_llm.py:323-324` |
| `Agent.kickoff(messages, response_format=...)` | `crewai/agent/core.py:1676` |

## Structured output and guardrails

| Claim | Source |
|---|---|
| `Task.response_model` is native provider structured output | `crewai/task.py:195` |
| YAML `output_pydantic` resolves to an `@output_pydantic` wrapper, which the task's validator turns into `None` | `crewai/project/crew_base.py:757`; `crewai/project/wrappers.py:417`; `crewai/task.py:109` |
| YAML `llm:` resolves to an `@llm` method, else a model string | `crewai/project/crew_base.py:665` |
| Guardrail takes one argument; annotated return must be `Tuple[bool, Any]` | `crewai/task.py:352, 369` |
| Guardrail result is unpacked as a tuple | `crewai/utilities/guardrail.py:115` |
| Raises after `guardrail_max_retries` | `crewai/task.py:1389` |
| `HallucinationGuardrail` is a no-op in open source | `crewai/tasks/hallucination_guardrail.py:75` |

## Memory and knowledge

| Claim | Source |
|---|---|
| Default memory embedder is OpenAI `text-embedding-3-large`; default analysis LLM `gpt-5.4-mini` | `crewai/memory/unified_memory.py:52, 89, 295` |
| `remember()` without an embedder raises `RuntimeError` | `crewai/memory/unified_memory.py:293` |
| Agent knowledge failure raises at kickoff | `crewai/agent/core.py:492` |
| Crew knowledge failure only logs | `crewai/crew.py:720`; `crewai/knowledge/storage/knowledge_storage.py:135` |
| Custom knowledge embedder type checks | `crewai/rag/embeddings/providers/custom/custom_provider.py:15`; `crewai/rag/embeddings/providers/custom/types.py:12` |
| Storage paths and `CREWAI_STORAGE_DIR` | `crewai/memory/storage/lancedb_storage.py:69`; `crewai_core/paths.py:13, 24`; `crewai/rag/chromadb/constants.py:11` |

## CLI

| Claim | Source |
|---|---|
| `create crew` is JSON by default; `--classic` for YAML | `crewai_cli/cli.py:163-165, 241, 271-273`; `crewai_cli/create_json_crew.py:443, 740-754` (`agents/<name>.jsonc`, `crew.jsonc`) |
| `run --inputs` only for declarative flows and crews | `crewai_cli/run_crew.py:674` |
| `reset-memories -s/-l/-e` are hidden aliases for `-m` | `crewai_cli/cli.py:427-445, 480` |
| `create flow` writes `.env` with a placeholder key | `crewai_cli/create_flow.py:56` |
