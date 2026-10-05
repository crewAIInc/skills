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
| One executor per agent cannot run concurrently (1.15.23) | `crewai/experimental/agent_executor.py:2869` ("Executor is already running") |

## Running and output

| Claim | Source |
|---|---|
| `kickoff` needs a dict | `crewai/crews/utils.py:282` |
| `kickoff_async` wraps sync `kickoff` in `asyncio.to_thread`; `akickoff` is native | `crewai/crew.py:1135, 1168, 1187, 1215` |
| `kickoff_for_each` | `crewai/crew.py:1099` |
| `kickoff_for_each` copies the crew per input; a copied task keeps the already-interpolated description (1.15.23) | `crewai/crew.py:1121`; `crewai/task.py:1154` |
| `token_usage` sums `agent.llm.get_token_usage_summary()` per agent, so a shared or reused `LLM` object is counted more than once (1.15.23) | `crewai/crew.py:2273-2293` (`calculate_usage_metrics`) |
| `https://` MCP string refs resolve with `asyncio.run()` (no tools inside a running event loop) (1.15.23) | `crewai/mcp/tool_resolver.py:552` (`_get_mcp_tool_schemas`) |
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
| crewai marks messages with a `cache_breakpoint` key (1.15.23) | `crewai/llms/cache.py:27` (`mark_cache_breakpoint`); `crewai/agents/crew_agent_executor.py:195` |

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
| `output_file` gets `json_dict` or the pydantic JSON when set, else `raw`; a leading `/` is stripped (1.15.23) | `crewai/task.py:782-790`, `:542` |

## Memory and knowledge

| Claim | Source |
|---|---|
| Default memory embedder is OpenAI `text-embedding-3-large`; default analysis LLM `gpt-5.4-mini` | `crewai/memory/unified_memory.py:52, 89, 295` |
| `remember()` without an embedder raises `RuntimeError` | `crewai/memory/unified_memory.py:293` |
| Agent knowledge failure raises at kickoff | `crewai/agent/core.py:492` |
| Agent knowledge is queried only on the task path (`execute_task` / `aexecute_task`), never by `Agent.kickoff()` (1.15.23) | `crewai/agent/core.py:979-986, 1121-1123` (`handle_knowledge_retrieval` calls); `kickoff` at `:1774` has none |
| Crew knowledge failure only logs | `crewai/crew.py:720`; `crewai/knowledge/storage/knowledge_storage.py:135` |
| Custom knowledge embedder type checks | `crewai/rag/embeddings/providers/custom/custom_provider.py:15`; `crewai/rag/embeddings/providers/custom/types.py:12` |
| `ollama` embedder needs the `ollama` Python package (1.15.23) | `chromadb/utils/embedding_functions/ollama_embedding_function.py:34` |
| Storage paths and `CREWAI_STORAGE_DIR` | `crewai/memory/storage/lancedb_storage.py:69`; `crewai_core/paths.py:13, 24`; `crewai/rag/chromadb/constants.py:11` |

## CLI

| Claim | Source |
|---|---|
| `create crew` is JSON by default; `--classic` for YAML | `crewai_cli/cli.py:163-165, 241, 271-273`; `crewai_cli/create_json_crew.py:443, 740-754` (`agents/<name>.jsonc`, `crew.jsonc`) |
| `run --inputs` only for declarative flows and crews | `crewai_cli/run_crew.py:674` |
| `reset-memories -s/-l/-e` are hidden aliases for `-m` | `crewai_cli/cli.py:427-445, 480` |
| `create flow` writes `.env` with a placeholder key | `crewai_cli/create_flow.py:56` |
| `CREWAI_DMN` non-interactive mode: default JSON crew on create, plain run without the run view (1.15.23; present in 1.15.22 too; not in the docs beyond a copy-paste setup prompt) | `crewai_cli/utils.py:79`; `crewai_cli/create_json_crew.py:760, 1304`; `crewai_cli/run_crew.py:334` |
| JSON crew run view exits 1 on failure; classic `crewai run` swallows the subprocess error (1.15.23) | `crewai_cli/run_crew.py:359`, `:822` |
| Scaffolds pin only `crewai[tools]`, no provider extra (1.15.23) | `crewai_cli/create_json_crew.py:1349`; classic `templates/crew/pyproject.toml` |
