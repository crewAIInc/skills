# Memory & Knowledge Reference

How to configure memory, knowledge sources, and embedders for crewAI agents and crews.

---

## Memory vs Knowledge

| Feature | Memory | Knowledge |
|---|---|---|
| **Purpose** | Learn from past executions | Access domain-specific data |
| **Persistence** | Across runs (long-term) or within run (short-term) | Always persistent |
| **Content** | Agent interactions, decisions, outcomes | Documents, files, structured data |
| **When to use** | Crews that improve over time | Agents that need reference material |

---

## 1. Memory Configuration

### Basic — Enable Default Memory

```python
from crewai import Crew

crew = Crew(
    agents=[...],
    tasks=[...],
    memory=True,  # Enable with defaults
)
```

### Custom Memory Configuration

```python
from crewai import Memory

memory = Memory(
    # Scoring weights (must sum to ~1.0)
    recency_weight=0.3,              # How much to favor recent memories
    semantic_weight=0.5,             # How much to favor semantic similarity
    importance_weight=0.2,           # How much to favor important memories

    # Behavior
    recency_half_life_days=30,       # Memory decay half-life
    consolidation_threshold=0.85,    # Dedup similarity threshold
    exploration_budget=1,            # Deep recall exploration rounds

    # LLM for memory analysis
    llm="openai/gpt-4o-mini",

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
# Create base memory
memory = Memory()

# Scope to specific agents
researcher_memory = memory.scope("/agent/researcher")
writer_memory = memory.scope("/agent/writer")

researcher = Agent(
    role="Researcher",
    goal="...",
    backstory="...",
    memory=researcher_memory,  # Only sees /agent/researcher memories
)
```

### Memory in Flows

```python
from crewai.flow.flow import Flow, start, listen

class ResearchFlow(Flow):

    @start()
    def gather_data(self):
        findings = "PostgreSQL handles 10k connections with pooling..."

        # Store memories
        self.remember(findings, scope="/research/databases")

    @listen(gather_data)
    def analyze(self, raw):
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
    content="Our company policy states that all deployments must be approved by two reviewers..."
)
```

### File-Based Knowledge

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
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
)
```

### Assigning Knowledge to Crews (Shared)

```python
crew = Crew(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    knowledge_sources=[text_source],  # All agents can access this
    embedder={
        "provider": "openai",
        "config": {"model": "text-embedding-3-small"},
    },
)
```

### Knowledge Configuration

```python
from crewai.knowledge.knowledge_config import KnowledgeConfig

agent = Agent(
    role="Researcher",
    goal="...",
    backstory="...",
    knowledge_sources=[pdf_source],
    knowledge_config=KnowledgeConfig(
        results_limit=10,        # Number of chunks to return (default: 3)
        score_threshold=0.5,     # Minimum relevance score (default: 0.35)
    ),
)
```

---

## 3. Embedder Configuration

Both memory and knowledge need an embedder for vector search. Configure at the agent or crew level.

### OpenAI (Default)

```python
embedder = {
    "provider": "openai",
    "config": {"model": "text-embedding-3-small"},
}
```

### Ollama (Local)

```python
embedder = {
    "provider": "ollama",
    "config": {
        "model": "mxbai-embed-large",
        "url": "http://localhost:11434",
    },
}
```

### Google

```python
embedder = {
    "provider": "google-generativeai",
    "config": {
        "model": "models/text-embedding-004",
        "api_key": "your-api-key",
    },
}
```

### Azure OpenAI

```python
embedder = {
    "provider": "azure",
    "config": {
        "model": "text-embedding-3-small",
        "api_key": "your-api-key",
        "api_base": "https://your-resource.openai.azure.com/",
        "api_type": "azure",
        "api_version": "2024-02-01",
    },
}
```

### Cohere

```python
embedder = {
    "provider": "cohere",
    "config": {
        "model": "embed-english-v3.0",
        "api_key": "your-api-key",
    },
}
```

### VoyageAI (Recommended for Claude)

```python
embedder = {
    "provider": "voyageai",
    "config": {
        "model": "voyage-3",
        "api_key": "your-api-key",
    },
}
```

### HuggingFace (Local)

```python
embedder = {
    "provider": "huggingface",
    "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"},
}
```

---

## 4. Storage Locations

Knowledge is stored locally by default:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/CrewAI/{project}/knowledge/` |
| Linux | `~/.local/share/CrewAI/{project}/knowledge/` |
| Windows | `C:\Users\{user}\AppData\Local\CrewAI\{project}\knowledge\` |

Override with environment variable:

```bash
export CREWAI_STORAGE_DIR="./my_project_storage"
```

---

## 5. Common Patterns

### Agent with Tools + Knowledge

```python
from crewai import Agent
from crewai_tools import SerperDevTool
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource

# Agent can both search the web AND reference internal docs
agent = Agent(
    role="Research Analyst",
    goal="Answer questions using internal docs and web research",
    backstory="...",
    tools=[SerperDevTool()],
    knowledge_sources=[PDFKnowledgeSource(file_paths=["internal_report.pdf"])],
    embedder={"provider": "openai", "config": {"model": "text-embedding-3-small"}},
)
```

### Crew with Shared Memory + Per-Agent Knowledge

```python
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    memory=True,              # Shared memory across agents
    embedder={...},           # Embedder for memory
)

# Each agent has its own knowledge sources
researcher = Agent(
    role="Researcher",
    knowledge_sources=[research_docs],
    ...
)

writer = Agent(
    role="Writer",
    knowledge_sources=[style_guide],
    ...
)
```
