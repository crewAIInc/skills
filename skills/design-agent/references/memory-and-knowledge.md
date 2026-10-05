# Memory & Knowledge Reference

How to configure memory, knowledge sources, and embedders for crewAI agents and crews.

Verified against crewai 1.15.23 on 2026-10-01; the memory and knowledge examples below were run with `anthropic/claude-haiku-4-5` and the local `onnx` embedder, with no OpenAI key.

---

## Memory vs Knowledge

| Feature | Memory | Knowledge |
|---|---|---|
| **Purpose** | Learn from past executions | Access domain-specific data |
| **Persistence** | One unified `Memory` (LanceDB) that persists across runs in the storage directory | Embedded once into a local Chroma collection, reused across runs |
| **Content** | Agent interactions, decisions, outcomes | Documents, files, structured data |
| **When to use** | Crews that improve over time | Agents that need reference material |

Both need an **embedder**, and both default to OpenAI embeddings. Memory also needs an **LLM** to analyze what it stores. Without `OPENAI_API_KEY` the defaults fail, mostly silently - see Section 4.

---

## 1. Memory Configuration

The old `ShortTermMemory`, `LongTermMemory` and `EntityMemory` classes and `memory_config` are gone (`memory_config` is silently ignored). There is one `Memory` class.

### Basic — Enable Default Memory

```python
from crewai import Crew

crew = Crew(
    agents=[...],
    tasks=[...],
    memory=True,                       # Memory for this crew
    embedder={"provider": "onnx"},     # used for memory too; omit for OpenAI embeddings
)
```

With `memory=True`, the crew builds `Memory` with the crew's `embedder` (OpenAI `text-embedding-3-large` when unset) and the first agent's `llm` for analysis. Verified live: a crew of `claude-haiku-4-5` agents with the `onnx` embedder stored "my project codename is BLUE HERON" in run 1, and a new crew answered "BLUE HERON" in run 2.

### Custom Memory Configuration

```python
from crewai import Memory

memory = Memory(
    # Scoring weights (keep them summing to about 1.0; not enforced)
    recency_weight=0.3,              # How much to favor recent memories
    semantic_weight=0.5,             # How much to favor semantic similarity
    importance_weight=0.2,           # How much to favor important memories

    # Behavior
    recency_half_life_days=30,       # Memory decay half-life
    consolidation_threshold=0.85,    # Dedup similarity threshold
    exploration_budget=1,            # Deep recall exploration rounds

    # LLM for memory analysis (default: OpenAI gpt-5.4-mini)
    llm="anthropic/claude-haiku-4-5",

    # Embedder (default: OpenAI text-embedding-3-large)
    embedder={"provider": "onnx"},

    # Storage backend (default: LanceDB)
    storage="lancedb",
)

crew = Crew(
    agents=[...],
    tasks=[...],
    memory=memory,
)
```

### Scoped Memory for Agents

```python
memory = Memory(llm="anthropic/claude-haiku-4-5", embedder={"provider": "onnx"})

researcher_memory = memory.scope("/agent/researcher")
writer_memory = memory.scope("/agent/writer")

researcher = Agent(
    role="Researcher",
    goal="...",
    backstory="...",
    memory=researcher_memory,  # Only sees /agent/researcher memories
)
```

Verified: a fact remembered through `memory.scope("/agent/researcher")` was the only result recalled through that scope. Direct use: `memory.remember("text", scope="/research/databases")` and `memory.recall("query", limit=10)`, which returns matches with `.record.content` and `.score` (`depth="shallow"` skips the LLM query-planning step).

### Memory in Flows

A Flow creates its own `Memory()` with the OpenAI defaults unless you give it one. Set it as a class attribute:

```python
from crewai import Memory
from crewai.flow import Flow, listen, start

class ResearchFlow(Flow):
    memory = Memory(llm="anthropic/claude-haiku-4-5", embedder={"provider": "onnx"})

    @start()
    def gather_data(self):
        findings = "PostgreSQL handles 10k connections with pooling..."
        self.remember(findings, scope="/research/databases")

    @listen(gather_data)
    def analyze(self):
        # Recall relevant memories (from this run or previous runs)
        past = self.recall("database performance", limit=10)
        for m in past:
            print(f"- {m.record.content}")
```

---

## 2. Knowledge Sources

Knowledge gives agents access to domain-specific documents via RAG.

### String Knowledge

```python
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

source = StringKnowledgeSource(
    content="Company policy states that all deployments must be approved by two reviewers..."
)
```

### File-Based Knowledge

File paths are relative to a `knowledge/` directory in the project root: `file_paths=["handbook.txt"]` reads `knowledge/handbook.txt`, and a missing file raises `FileNotFoundError: File not found: knowledge/handbook.txt`.

```python
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource
from crewai.knowledge.source.csv_knowledge_source import CSVKnowledgeSource

text_source = TextFileKnowledgeSource(file_paths=["handbook.txt", "faq.txt"])
pdf_source = PDFKnowledgeSource(file_paths=["policy.pdf"])
csv_source = CSVKnowledgeSource(file_paths=["products.csv"])
```

### Assigning Knowledge to Agents

```python
agent = Agent(
    role="Policy Expert",
    goal="Answer questions based on company policy",
    backstory="...",
    knowledge_sources=[text_source, pdf_source],
    embedder={"provider": "onnx"},
)
```

Agent knowledge is only queried when the agent runs a task inside a `Crew`. `agent.kickoff(...)` ignores it silently: in a live test, the same agent answered "UNKNOWN" from `kickoff()` and correctly from a one-task crew.

### Assigning Knowledge to Crews (Shared)

```python
crew = Crew(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    knowledge_sources=[text_source],  # All agents can access this
    embedder={"provider": "onnx"},
)
```

A crew whose knowledge fails to embed still constructs and runs, and only logs `Failed to upsert documents: ...`. If the crew must not run without its knowledge, check the log or test the answer.

### Knowledge Configuration

```python
from crewai.knowledge.knowledge_config import KnowledgeConfig

agent = Agent(
    role="Researcher",
    goal="...",
    backstory="...",
    knowledge_sources=[pdf_source],
    knowledge_config=KnowledgeConfig(
        results_limit=10,        # Number of chunks to return (default: 5)
        score_threshold=0.5,     # Minimum relevance score (default: 0.6)
    ),
)
```

---

## 3. Embedder Configuration

Both memory and knowledge need an embedder for vector search. Configure it at the agent or crew level, or on `Memory(embedder=...)`. The shape is `{"provider": <name>, "config": {...}}`. The model key is `model_name` for most providers; `"model"` raises `TypeError: OpenAIEmbeddingFunction.__init__() got an unexpected keyword argument 'model'` for OpenAI. Most providers also need their Python package installed - constructing the embedder without it raises an error naming the package.

### ONNX (Local, no API key) - verified working

```python
embedder = {"provider": "onnx"}
```

Runs `all-MiniLM-L6-v2` locally through `onnxruntime`, which core crewai already installs (via chromadb). The first use downloads the model (about 80 MB) to `~/.cache/chroma/onnx_models/`. This is the simplest way to run memory and knowledge with a non-OpenAI LLM.

### OpenAI (Default)

```python
embedder = {
    "provider": "openai",
    "config": {"model_name": "text-embedding-3-small"},   # default: text-embedding-3-large
}
```

### Ollama (Local)

```python
embedder = {
    "provider": "ollama",
    "config": {
        "model_name": "mxbai-embed-large",
        "url": "http://localhost:11434/api/embeddings",   # the default
    },
}
```

Needs the `ollama` package and a running Ollama server.

### Google

```python
embedder = {
    "provider": "google-generativeai",
    "config": {
        "model_name": "gemini-embedding-001",   # or text-embedding-005, text-multilingual-embedding-002
        "api_key": "your-api-key",
    },
}
```

Any other model name (for example `models/text-embedding-004`) is a `ValidationError`.

### Azure OpenAI

```python
embedder = {
    "provider": "azure",
    "config": {
        "deployment_id": "your-embedding-deployment",   # required
        "model_name": "text-embedding-3-small",
        "api_key": "your-api-key",
        "api_base": "https://your-resource.openai.azure.com/",
        "api_version": "2024-02-01",
    },
}
```

Without `deployment_id`: `ValidationError: 1 validation error for AzureProvider ... EMBEDDINGS_OPENAI_DEPLOYMENT_ID Field required`.

### Cohere

```python
embedder = {
    "provider": "cohere",
    "config": {
        "model_name": "embed-english-v3.0",
        "api_key": "your-api-key",
    },
}
```

### VoyageAI (Recommended for Claude)

```python
embedder = {
    "provider": "voyageai",
    "config": {
        "model": "voyage-3",    # VoyageAI uses "model", not "model_name"
        "api_key": "your-api-key",
    },
}
```

Needs `uv add voyageai`.

### Sentence Transformers (Local) and HuggingFace (Hosted)

```python
embedder = {"provider": "sentence-transformer", "config": {"model_name": "all-MiniLM-L6-v2"}}  # local, needs sentence-transformers
embedder = {"provider": "huggingface", "config": {"model_name": "sentence-transformers/all-MiniLM-L6-v2"}}  # HF Inference API
```

The `huggingface` provider calls the hosted Inference API and needs a token (`HF_TOKEN` or `api_key`); it is not local.

---

## 4. Failure Modes Without an OpenAI Key

All observed on 1.15.23 with `OPENAI_API_KEY` unset and an Anthropic LLM:

| Setup | What happens |
|---|---|
| `Crew(memory=True)`, no `embedder` | Crew **completes**; every memory save fails with only a `memory_save_failed` event, and nothing is stored |
| `Memory().remember(...)` | `RuntimeError: Memory requires an embedder for vector search but initialization failed: ...` |
| Agent `knowledge_sources`, no `embedder`, agent in a crew | `ValueError: Invalid Knowledge Configuration: The OPENAI_API_KEY environment variable is not set.` at kickoff |
| Same agent via `agent.kickoff()` | Runs; knowledge silently unused |
| Crew `knowledge_sources`, no `embedder` | Logs `Failed to upsert documents`; crew runs **without** knowledge |

With an invalid key, the same rows fail with `Error code: 401` instead. Fix: pass an `embedder` (and for memory an `llm`) explicitly.

---

## 5. Storage Locations

Memory, knowledge and the other local stores live under one storage directory:

| `CREWAI_STORAGE_DIR` | Directory |
|---|---|
| unset | `<platform data dir>/<project directory name>/` - on macOS `~/Library/Application Support/<project>/`, on Linux `~/.local/share/<project>/` |
| absolute path | that path |
| relative name, e.g. `./my_project_storage` | split: knowledge and the SQLite files go under the platform data dir (`~/Library/Application Support/my_project_storage` on macOS), but memory goes to `./my_project_storage/memory` relative to the current directory |

```bash
export CREWAI_STORAGE_DIR="$PWD/.crewai_storage"   # use an absolute path
```

Inside it: `memory/` (LanceDB), `chroma.sqlite3` plus collection folders (knowledge), and `latest_kickoff_task_outputs.db`.

A knowledge collection remembers the embedder that created it. Switching embedders on existing storage fails with `Failed to upsert documents: An embedding function already exists in the collection configuration, and a new one is provided.` Reset with `crewai reset-memories -kn` (knowledge) or `-akn` (agent knowledge), or use a fresh storage directory.

---

## 6. Common Patterns

### Agent with Tools + Knowledge (run inside a crew)

```python
from crewai import Agent, Crew, Task
from crewai_tools import SerperDevTool
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource

# Agent can both search the web AND reference internal docs
agent = Agent(
    role="Research Analyst",
    goal="Answer questions using internal docs and web research",
    backstory="...",
    tools=[SerperDevTool()],
    knowledge_sources=[PDFKnowledgeSource(file_paths=["internal_report.pdf"])],
    embedder={"provider": "onnx"},
)
crew = Crew(agents=[agent], tasks=[Task(description="...", expected_output="...", agent=agent)])
```

### Crew with Shared Memory + Per-Agent Knowledge

```python
researcher = Agent(
    role="Researcher", goal="...", backstory="...",
    knowledge_sources=[research_docs],
    embedder={"provider": "onnx"},
)

writer = Agent(
    role="Writer", goal="...", backstory="...",
    knowledge_sources=[style_guide],
    embedder={"provider": "onnx"},
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    memory=True,                       # Shared memory across agents
    embedder={"provider": "onnx"},     # Embedder for memory
)
```

For deterministic offline tests (a callable embedder and stub LLM), see the **check-crewai-api** skill's verify-installed-api reference and **test-crewai-project**.
