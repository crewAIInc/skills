# CrewAI Tools Catalog

Quick reference for all built-in tools. All imports from `crewai_tools` unless noted.

> **Prefer official MCP servers over native tools when available.** Official MCP servers are maintained by the service providers and stay up to date automatically. See [MCP Servers Reference](mcp-servers.md) for the full guide. Fall back to the native tools below only when no official MCP server exists for the service you need.

---

## Search & Research

| Tool | Purpose | Env Var | Import |
|---|---|---|---|
| `SerperDevTool` | Google search via Serper.dev | `SERPER_API_KEY` | `from crewai_tools import SerperDevTool` |
| `BraveWebSearchTool` | Privacy-focused web search | `BRAVE_API_KEY` | `from crewai_tools import BraveWebSearchTool` |
| `EXASearchTool` | AI-powered semantic search | `EXA_API_KEY` | `from crewai_tools import EXASearchTool` |
| `TavilySearchTool` | Comprehensive web search | `TAVILY_API_KEY` | `from crewai_tools import TavilySearchTool` |
| `TavilyExtractorTool` | Extract structured content from URLs | `TAVILY_API_KEY` | `from crewai_tools import TavilyExtractorTool` |
| `SerpApiGoogleSearchTool` | Google search via SerpApi | `SERPAPI_API_KEY` | `from crewai_tools import SerpApiGoogleSearchTool` |
| `SerpApiGoogleShoppingTool` | Google Shopping search | `SERPAPI_API_KEY` | `from crewai_tools import SerpApiGoogleShoppingTool` |
| `LinkupSearchTool` | Contextual search via Linkup | — | `from crewai_tools import LinkupSearchTool` |
| `ArxivPaperTool` | Search arXiv for academic papers | — | `from crewai_tools import ArxivPaperTool` |
| `GithubSearchTool` | RAG search in GitHub repos | `gh_token` param | `from crewai_tools import GithubSearchTool` |
| `CodeDocsSearchTool` | RAG search in code documentation | — | `from crewai_tools import CodeDocsSearchTool` |

## Web Scraping

| Tool | Purpose | Env Var | Import |
|---|---|---|---|
| `ScrapeWebsiteTool` | Extract website content via HTTP | — | `from crewai_tools import ScrapeWebsiteTool` |
| `ScrapeElementFromWebsiteTool` | Scrape specific HTML elements via CSS selectors | — | `from crewai_tools import ScrapeElementFromWebsiteTool` |
| `SeleniumScrapingTool` | Scrape dynamic JS-rendered content | — | `from crewai_tools import SeleniumScrapingTool` |
| `FirecrawlScrapeWebsiteTool` | High-performance scraping | `FIRECRAWL_API_KEY` | `from crewai_tools import FirecrawlScrapeWebsiteTool` |
| `FirecrawlCrawlWebsiteTool` | Crawl entire websites | `FIRECRAWL_API_KEY` | `from crewai_tools import FirecrawlCrawlWebsiteTool` |
| `FirecrawlSearchTool` | Search + extract with Firecrawl | `FIRECRAWL_API_KEY` | `from crewai_tools import FirecrawlSearchTool` |
| `SpiderTool` | Comprehensive web crawling | — | `from crewai_tools import SpiderTool` |
| `BrowserbaseLoadTool` | Cloud browser automation | `BROWSERBASE_API_KEY` | `from crewai_tools import BrowserbaseLoadTool` |
| `StagehandTool` | Natural language browser automation | — | `from crewai_tools import StagehandTool` |

## File & Document

| Tool | Purpose | Import |
|---|---|---|
| `FileReadTool` | Read local files (.txt, .csv, .json, etc.) | `from crewai_tools import FileReadTool` |
| `FileWriterTool` | Write content to files | `from crewai_tools import FileWriterTool` |
| `DirectoryReadTool` | List directory contents | `from crewai_tools import DirectoryReadTool` |
| `DirectorySearchTool` | RAG search within directories | `from crewai_tools import DirectorySearchTool` |
| `PDFSearchTool` | RAG search within PDFs | `from crewai_tools import PDFSearchTool` |
| `PDFTextWritingTool` | Write text at coordinates in PDFs | `from crewai_tools import PDFTextWritingTool` |
| `DOCXSearchTool` | RAG search within Word docs | `from crewai_tools import DOCXSearchTool` |
| `CSVSearchTool` | RAG search within CSV files | `from crewai_tools import CSVSearchTool` |
| `JSONSearchTool` | RAG search within JSON files | `from crewai_tools import JSONSearchTool` |
| `XMLSearchTool` | RAG search within XML files | `from crewai_tools import XMLSearchTool` |
| `MDXSearchTool` | RAG search within Markdown files | `from crewai_tools import MDXSearchTool` |
| `TXTSearchTool` | RAG search within text files | `from crewai_tools import TXTSearchTool` |
| `OCRTool` | Extract text from images via vision LLM | `from crewai_tools import OCRTool` |

## Database

| Tool | Purpose | Dependencies | Import |
|---|---|---|---|
| `NL2SQLTool` | Natural language to SQL | SQLAlchemy + driver | `from crewai_tools import NL2SQLTool` |
| `PGSearchTool` | RAG search in PostgreSQL | — | `from crewai_tools import PGSearchTool` |
| `MySQLSearchTool` | RAG search in MySQL | — | `from crewai_tools import MySQLSearchTool` |
| `DatabricksQueryTool` | SQL queries on Databricks | — | `from crewai_tools import DatabricksQueryTool` |
| `SnowflakeSearchTool` | SQL queries on Snowflake | snowflake-connector | `from crewai_tools import SnowflakeSearchTool` |
| `SingleStoreSearchTool` | SELECT queries on SingleStore | crewai-tools[singlestore] | `from crewai_tools import SingleStoreSearchTool` |

## Vector Databases

| Tool | Purpose | Dependencies | Import |
|---|---|---|---|
| `QdrantVectorSearchTool` | Vector search via Qdrant | qdrant-client | `from crewai_tools import QdrantVectorSearchTool` |
| `WeaviateVectorSearchTool` | Vector search via Weaviate | weaviate-client | `from crewai_tools import WeaviateVectorSearchTool` |
| `MongoDBVectorSearchTool` | Vector search on MongoDB Atlas | crewai-tools[mongodb] | `from crewai_tools import MongoDBVectorSearchTool` |

## AI & Code

| Tool | Purpose | Env Var | Import |
|---|---|---|---|
| `DallETool` | Generate images with DALL-E | `OPENAI_API_KEY` | `from crewai_tools import DallETool` |
| `VisionTool` | Extract text from images | `OPENAI_API_KEY` | `from crewai_tools import VisionTool` |
| `CodeInterpreterTool` | Execute Python in Docker sandbox | Docker required | `from crewai_tools import CodeInterpreterTool` |
| `RagTool` | General-purpose RAG for any data source | — | `from crewai_tools import RagTool` |
| `LlamaIndexTool` | Wrap LlamaIndex tools/query engines | llama-index | `from crewai_tools import LlamaIndexTool` |

## Cloud & AWS

| Tool | Purpose | Env Var | Import |
|---|---|---|---|
| `S3ReaderTool` | Read files from S3 | `CREW_AWS_*` | `from crewai_tools.aws.s3 import S3ReaderTool` |
| `S3WriterTool` | Write files to S3 | `CREW_AWS_*` | `from crewai_tools.aws.s3 import S3WriterTool` |
| `BedrockKBRetriever` | Query Bedrock knowledge bases | AWS creds | `from crewai_tools import BedrockKBRetriever` |
| `BedrockInvokeAgentTool` | Call Bedrock Agents | AWS creds | `from crewai_tools.aws.bedrock.agents.invoke_agent_tool import BedrockInvokeAgentTool` |

## YouTube

| Tool | Purpose | Import |
|---|---|---|
| `YoutubeVideoSearchTool` | RAG search within YouTube videos | `from crewai_tools import YoutubeVideoSearchTool` |
| `YoutubeChannelSearchTool` | RAG search within YouTube channels | `from crewai_tools import YoutubeChannelSearchTool` |

## Automation & Integration

| Tool | Purpose | Env Var | Import |
|---|---|---|---|
| `ApifyActorsTool` | Run Apify web scraping actors | `APIFY_API_TOKEN` | `from crewai_tools import ApifyActorsTool` |
| `ComposioToolSet` | 250+ tools via Composio platform | `COMPOSIO_API_KEY` | `from composio_crewai import ComposioProvider` |
| `MultiOnTool` | Browser workflow automation | — | `from crewai_tools import MultiOnTool` |
| `ZapierActionsAdapter` | Zapier actions as CrewAI tools | `ZAPIER_API_KEY` | `from crewai_tools.adapters.zapier_adapter import ZapierActionsAdapter` |
| `MergeAgentHandlerTool` | 250+ tools via Merge unified API | `AGENT_HANDLER_API_KEY` | `from crewai_tools import MergeAgentHandlerTool` |
| `InvokeCrewAIAutomationTool` | Invoke CrewAI Platform automations | `CREWAI_API_URL` | `from crewai_tools import InvokeCrewAIAutomationTool` |

---

## Common Tool Patterns

### Search + Scrape (most common combo)

```python
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

researcher = Agent(
    role="Researcher",
    goal="Research topics thoroughly",
    backstory="...",
    tools=[SerperDevTool(), ScrapeWebsiteTool()],
)
```

### File Reading + Writing

```python
from crewai_tools import FileReadTool, FileWriterTool

agent = Agent(
    role="File Processor",
    goal="Read and transform files",
    backstory="...",
    tools=[FileReadTool(), FileWriterTool()],
)
```

### RAG over Documents

```python
from crewai_tools import PDFSearchTool, DirectorySearchTool

agent = Agent(
    role="Document Analyst",
    goal="Analyze document collections",
    backstory="...",
    tools=[
        PDFSearchTool(pdf="/path/to/doc.pdf"),
        DirectorySearchTool(directory="/path/to/docs/"),
    ],
)
```
