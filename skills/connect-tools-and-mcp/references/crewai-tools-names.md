# crewai_tools Names Reference

What `crewai_tools` 1.15.22-1.15.23 actually exports, the names models invent, and what each tool needs before it will construct.

---

## 1. Check before you write

```python
import crewai_tools

def has_tool(name: str) -> bool:
    return hasattr(crewai_tools, name)

for name in ["SerperDevTool", "CodeInterpreterTool", "BedrockKBRetrieverTool"]:
    print(name, has_tool(name))   # True / False / True
```

Run `crewai version --tools` to see the installed crewai-tools version. Every name below was checked by import against crewai-tools 1.15.22-1.15.23.

---

## 2. All exported names (1.15.22-1.15.23)

`crewai_tools` has 118 public names: 113 classes plus the submodules `adapters`, `aws`, `rag`, `security`, `tools`.

| Area | Names |
|---|---|
| Web search | `SerperDevTool`, `BraveSearchTool`, `BraveWebSearchTool`, `BraveNewsSearchTool`, `BraveImageSearchTool`, `BraveVideoSearchTool`, `BraveLocalPOIsTool`, `BraveLocalPOIsDescriptionTool`, `BraveLLMContextTool`, `EXASearchTool`, `ExaSearchTool`, `TavilySearchTool`, `TavilyExtractorTool`, `TavilyResearchTool`, `TavilyGetResearchTool`, `LinkupSearchTool`, `ParallelSearchTool`, `SerpApiGoogleSearchTool`, `SerpApiGoogleShoppingTool`, `SerplyWebSearchTool`, `SerplyNewsSearchTool`, `SerplyScholarSearchTool`, `SerplyJobSearchTool`, `BrightDataSearchTool`, `OxylabsGoogleSearchScraperTool`, `ArxivPaperTool` |
| Scraping and browsing | `ScrapeWebsiteTool`, `ScrapeElementFromWebsiteTool`, `SerperScrapeWebsiteTool`, `SerplyWebpageToMarkdownTool`, `FirecrawlScrapeWebsiteTool`, `FirecrawlCrawlWebsiteTool`, `FirecrawlSearchTool`, `JinaScrapeWebsiteTool`, `ScrapflyScrapeWebsiteTool`, `ScrapegraphScrapeTool`, `ScrapegraphScrapeToolSchema`, `SpiderTool`, `SeleniumScrapingTool`, `BrowserbaseLoadTool`, `HyperbrowserLoadTool`, `StagehandTool`, `BrightDataWebUnlockerTool`, `BrightDataDatasetTool`, `OxylabsUniversalScraperTool`, `OxylabsAmazonProductScraperTool`, `OxylabsAmazonSearchScraperTool`, `URLReadTool`, `MultiOnTool` |
| Files and directories | `FileReadTool`, `FileWriterTool`, `FileCompressorTool`, `DirectoryReadTool` |
| RAG search (need an embedder) | `RagTool`, `WebsiteSearchTool`, `PDFSearchTool`, `CSVSearchTool`, `JSONSearchTool`, `TXTSearchTool`, `DOCXSearchTool`, `MDXSearchTool`, `XMLSearchTool`, `DirectorySearchTool`, `CodeDocsSearchTool`, `GithubSearchTool`, `YoutubeVideoSearchTool`, `YoutubeChannelSearchTool`, `MySQLSearchTool` |
| Databases and vector stores | `NL2SQLTool`, `DatabricksQueryTool`, `SnowflakeSearchTool`, `SnowflakeConfig`, `SingleStoreSearchTool`, `QdrantVectorSearchTool`, `WeaviateVectorSearchTool`, `MongoDBVectorSearchTool`, `MongoDBVectorSearchConfig`, `CouchbaseFTSVectorSearchTool`, `DB2VectorSearchTool`, `DB2ToolSchema` |
| Code sandboxes | `E2BPythonTool`, `E2BExecTool`, `E2BFileTool`, `DaytonaPythonTool`, `DaytonaExecTool`, `DaytonaFileTool` |
| Vision and media | `DallETool`, `VisionTool`, `OCRTool` |
| AWS | `S3ReaderTool`, `S3WriterTool`, `BedrockKBRetrieverTool`, `BedrockInvokeAgentTool` |
| Integrations and platforms | `MCPServerAdapter`, `ComposioTool`, `ZapierActionTool`, `ZapierActionTools`, `ApifyActorsTool`, `MergeAgentHandlerTool`, `LlamaIndexTool`, `CrewaiPlatformTools`, `EnterpriseActionTool`, `InvokeCrewAIAutomationTool`, `GenerateCrewaiAutomationTool`, `AIMindTool` |
| Contextual AI, evaluation | `ContextualAICreateAgentTool`, `ContextualAIParseTool`, `ContextualAIQueryTool`, `ContextualAIRerankTool`, `PatronusEvalTool`, `PatronusLocalEvaluatorTool`, `PatronusPredefinedCriteriaEvalTool` |
| Utility | `WaitTool` |

Deeper import paths that also work: `from crewai_tools.aws.s3 import S3ReaderTool`, `from crewai_tools.adapters.zapier_adapter import ZapierActionsAdapter`, `from crewai_tools.adapters.mcp_adapter import MCPServerAdapter`.

---

## 3. Names that do not exist (ImportError in 1.15.22-1.15.23)

| Name | Use instead |
|---|---|
| `BaseTool`, `tool` | `from crewai.tools import BaseTool, tool` |
| `CodeInterpreterTool` | `E2BPythonTool` or `DaytonaPythonTool` (the Agent flags `allow_code_execution` / `code_execution_mode` are deprecated no-ops) |
| `BedrockKBRetriever` | `BedrockKBRetrieverTool` |
| `GitHubSearchTool`, `GithubTool` | `GithubSearchTool` |
| `ArxivTool` | `ArxivPaperTool` |
| `ComposioToolSet` | `ComposioTool` |
| `ZapierActionsAdapter` (top level) | `ZapierActionTools`, or the `crewai_tools.adapters.zapier_adapter` path |
| `YoutubeSearchTool` | `YoutubeVideoSearchTool` / `YoutubeChannelSearchTool` |
| `SeleniumTool`, `BrowserTool`, `PlaywrightTool` | `SeleniumScrapingTool`, `BrowserbaseLoadTool`, `StagehandTool` |
| `GoogleSearchTool`, `WebSearchTool`, `DuckDuckGoSearchTool` | `SerperDevTool`, `BraveSearchTool`, `TavilySearchTool`, `EXASearchTool` |
| `PDFTextWritingTool`, `PGSearchTool`, `WikipediaTool`, `WikipediaSearchTool`, `PythonREPLTool`, `ShellTool`, `BashTool`, `CalculatorTool`, `SQLTool`, `EmailTool`, `SlackTool`, `GmailTool`, `HumanTool`, `AskHumanTool`, `LangChainTool` | No equivalent - write a custom tool, or use an MCP server for that service |

---

## 4. What a tool needs before it constructs

Constructed with no API keys in the environment (crewai-tools 1.15.22-1.15.23):

| Tool | Result |
|---|---|
| `SerperDevTool()`, `ScrapeWebsiteTool()`, `FileReadTool()`, `FileWriterTool()`, `DirectoryReadTool()`, `ArxivPaperTool()` | Construct fine. Keyed tools fail only when called |
| `BraveSearchTool()` | `ValueError: BRAVE_API_KEY environment variable is required for BraveSearchTool` |
| `WebsiteSearchTool()`, `PDFSearchTool()` (all RAG tools) | `ValidationError ... The OPENAI_API_KEY environment variable is not set.` - they build an embedder at construction |
| `EXASearchTool()`, `TavilySearchTool()`, `FirecrawlSearchTool()`, `SeleniumScrapingTool()` | Interactive prompt `You are missing the '<pkg>' package. Would you like to install it? [y/N]` - blocks under a terminal, `click.exceptions.Abort` with stdin closed |
| `StagehandTool()` | `ImportError: \`stagehand\` package not found, please run \`uv add stagehand\`` |
| `MCPServerAdapter(...)` | Same interactive prompt, worded as the `'mcp'` package, until `crewai-tools[mcp]` is installed |

Install the extra before the first run so no prompt can ever block a scripted run, CI job or deployment:

```bash
uv add "crewai[tools]"                 # crewai-tools itself (the scaffold already depends on this)
uv add "crewai-tools[mcp]"             # MCPServerAdapter
uv add "crewai-tools[exa-py]"          # EXASearchTool
uv add "crewai-tools[tavily-python]"   # TavilySearchTool
uv add "crewai-tools[firecrawl-py]"    # Firecrawl*
uv add "crewai-tools[selenium]"        # SeleniumScrapingTool
```

All crewai-tools 1.15.22-1.15.23 extras: `apify beautifulsoup4 bedrock browserbase composio-core contextual couchbase databricks-sdk daytona e2b exa-py firecrawl-py github hyperbrowser linkup-sdk mcp mongodb multion mysql oxylabs patronus postgresql qdrant-client rag scrapegraph-py scrapfly-sdk selenium serpapi singlestore snowflake spider-client sqlalchemy stagehand tavily-python weaviate-client xml`.

For RAG tools without OpenAI, pass `config={"embedding_model": {"provider": "<provider>", "config": {...}}}` at construction. The provider's own package must be installed: `provider="ollama"` without the `ollama` package fails with `The ollama python package is not installed`. Per-tool options are documented under https://docs.crewai.com/en/tools/overview.
