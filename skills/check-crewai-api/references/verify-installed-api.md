# Verify the installed crewai API

One-liners to check a parameter, default, or signature against the crewai that is actually installed, instead of trusting memory or a tutorial.

Run them with the project's interpreter (`uv run python ...` inside a crewai project).

---

## 1. Version

```bash
crewai version
uv run python -c "import crewai; print(crewai.__version__)"
```

The CLI is a separate package (`crewai_cli`); `crewai version` and `import crewai` should agree. If they do not, the project venv and the global CLI differ - trust the project venv.

---

## 2. Does this parameter exist, and what is its default?

`Agent`, `Task` and `Crew` silently drop unknown keyword arguments, so the only reliable check is the model's field list.

```python
from crewai import Agent, Crew, Task

for cls, name in [(Task, "response_model"), (Task, "response_format"),
                  (Crew, "memory_config"), (Agent, "max_iter"), (Crew, "cache")]:
    field = cls.model_fields.get(name)
    if field is None:
        print(f"{cls.__name__}.{name}: NOT A FIELD - silently ignored if passed")
    else:
        print(f"{cls.__name__}.{name}: default={field.default!r} deprecated={field.deprecated!r}")
```

Expected on 1.15.22-1.15.23: `Task.response_model` default `None`; `Task.response_format` and `Crew.memory_config` are not fields; `Agent.max_iter` default `25`; `Crew.cache` default `False`.

---

## 3. What signature does this method take?

```python
import inspect

from crewai import LLM, Agent, Crew

print(inspect.signature(Crew.kickoff))
print(inspect.signature(Crew.akickoff))
print(inspect.signature(Agent.kickoff))
print(inspect.signature(type(LLM(model="openai/gpt-4.1-mini")).call))
print(inspect.getsourcefile(Crew.kickoff))
```

`LLM(...)` is a factory, so inspect `type(LLM(...))` (for example `OpenAICompletion`), not `LLM` itself. Constructing it needs no API key.

---

## 4. Which model will an agent use?

```python
import os

from crewai import Agent

os.environ["MODEL"] = "openai/gpt-4o-mini"
agent = Agent(role="r", goal="g", backstory="b")
print(type(agent.llm).__name__, agent.llm.model)
```

Resolution order when `llm=` is not set: `MODEL`, `MODEL_NAME`, `OPENAI_MODEL_NAME`, then `gpt-4.1-mini`. The provider key is only checked at kickoff.

---

## 5. Where memory and knowledge are stored

- Memory (LanceDB): `$CREWAI_STORAGE_DIR/memory` when the variable is set, otherwise `<platform data dir>/<project dir name>/memory` (on macOS `~/Library/Application Support/<project dir name>/memory`).
- SQLite stores (`latest_kickoff_task_outputs.db`, flow state) and knowledge (Chroma): `<platform data dir>/<CREWAI_STORAGE_DIR or project dir name>`.
- Set `CREWAI_STORAGE_DIR` to an **absolute** path in tests and CI so every store lands in one directory you can delete.

---

## 6. Memory and knowledge without an API key

Both default to OpenAI embeddings. To run offline (tests, CI), give `Memory` an LLM you control and a callable embedder, and give knowledge a custom embedding class.

A `Memory` embedder is any callable `list[str] -> list[list[float]]`:

```python
from crewai import Memory


def embed(texts: list[str]) -> list[list[float]]:
    return [[float(len(t) % 7), 1.0, 0.5] for t in texts]


memory = Memory(llm="openai/gpt-4.1-mini", embedder=embed, storage="./.test_memory")
```

A knowledge embedder must subclass both crewai's `CustomEmbeddingFunction` (checked by the knowledge storage) and chromadb's `EmbeddingFunction` (checked by `Crew(embedder=...)`):

```python
from chromadb import EmbeddingFunction

from crewai import Agent, Crew, Task
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource
from crewai.rag.embeddings.providers.custom.embedding_callable import CustomEmbeddingFunction


class ConstantEmbedding(CustomEmbeddingFunction, EmbeddingFunction):
    def __init__(self):
        pass

    def __call__(self, input):
        return [[1.0, 0.0, 0.0] for _ in input]

    @staticmethod
    def name():
        return "constant"


agent = Agent(role="Analyst", goal="Answer", backstory="Uses knowledge.", llm="openai/gpt-4.1-mini")
task = Task(description="When was acme founded?", expected_output="A year.", agent=agent)
crew = Crew(
    agents=[agent],
    tasks=[task],
    knowledge_sources=[StringKnowledgeSource(content="acme was founded in 2020.")],
    embedder={"provider": "custom", "config": {"embedding_callable": ConstantEmbedding}},
)
assert crew.knowledge is not None, "knowledge failed to initialise"
```

Check `crew.knowledge is not None` after construction: crew-level knowledge that fails to initialise only logs a warning.
