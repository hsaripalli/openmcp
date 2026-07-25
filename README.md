# opendata.fyi — Explore public data with your AI assistant

An open-source MCP server that lets AI assistants and MCP clients (Claude,
Cursor, Codex, ChatGPT, Gemini CLI, Zed, and others) discover and query public
datasets published through [open.canada.ca](https://open.canada.ca), with more
sources coming soon.

Ask *"how do interest rates affect housing prices?"* and your AI assistant can
use opendata.fyi to find relevant datasets, query their resources, and answer
with source links—without manual downloads or hunting through the portal.

**Zero API keys required.** Semantic search runs on a local embedding model (bge-small-en-v1.5 via [fastembed](https://github.com/qdrant/fastembed)); data querying is powered by CKAN's public API and DuckDB.

## How it works

```
"which neighbourhoods in Toronto have the worst air quality?"
        │
        ▼
semantic_search_datasets ──── hybrid search: local vector index (24k datasets,
        │                     DuckDB + bge-small embeddings) fused with the
        │                     portal's keyword search via Reciprocal Rank Fusion
        ▼
get_dataset ────────────────── resources + which are API-queryable
        │
        ├─ datastore-backed? ──▶ query_datastore    (server-side, no download)
        ├─ CSV / Parquet?    ──▶ query_remote_file  (DuckDB streams over HTTP)
        ├─ ZIP of CSV?       ──▶ query_remote_file  (auto-extracted — StatCan bulk files)
        ├─ Excel?            ──▶ list_excel_sheets → query_excel_sheet
        └─ PDF report?       ──▶ read_pdf           (page-ranged text extraction)
```

Every response includes a source link back to open.canada.ca.

## Quick start

```bash
git clone https://github.com/opendatafyi/openmcp.git
cd openmcp
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### Get the search index

The semantic index (`catalog.duckdb`, ~120MB) is too large for git. Download it
from the [latest release](https://github.com/opendatafyi/openmcp/releases) and put it in the project root.

### Client Setup (Universal MCP Standard)

opendata.fyi uses the standard **MCP stdio protocol**, making it compatible out of the box with any MCP client application (**Claude Desktop**, **Claude Code**, **Gemini CLI**, **ChatGPT Desktop**, **Cursor**, **Cline / Roo Code**, **Windsurf**, **Zed**, **Continue.dev**, **Goose**, etc.).

Add this standard JSON block to your client's MCP configuration file (e.g. `claude_desktop_config.json`, `.mcp.json`, `cline_mcp_settings.json`, `mcp_config.json`):

```json
{
  "mcpServers": {
    "openmcp": {
      "command": "/absolute/path/to/openmcp/venv/bin/python",
      "args": ["/absolute/path/to/openmcp/mcp_server.py"]
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `semantic_search_datasets(query)` | Hybrid semantic + keyword dataset discovery (RRF) |
| `search_datasets(query)` | Plain keyword search (CKAN `package_search`) |
| `get_dataset(id)` | A dataset's resources + which are API-queryable |
| `get_resource_fields(resource_id)` | Columns/types of a datastore resource, no download |
| `query_datastore(resource_id, ...)` | **Server-side** filter/search — the fast path |
| `get_file_schema(url)` | Schema of a remote file (DuckDB `DESCRIBE`, minimal download) |
| `preview_remote_file(url)` | First rows of a remote CSV/Parquet/JSON/Excel/ZIP |
| `query_remote_file(url, sql)` | Read-only DuckDB SQL on a remote file (ZIP auto-extracted) |
| `list_excel_sheets(url)` | Sheets, shapes, and columns of a workbook (header auto-detected) |
| `query_excel_sheet(url, sheet, sql)` | SQL against one sheet of a workbook |
| `read_pdf(url, pages)` | Page-ranged text extraction from PDF resources |

Plus three MCP prompts (`query_canada_data`, `explore_dataset`,
`compare_datasets`) that encode the full workflow for one-click use.

## Design notes

- **Server-side first.** Resources with `datastore_active: true` are filtered by
  the portal's own database (`datastore_search`) — only matching rows travel.
  Files are the fallback, streamed by DuckDB over HTTP range requests where
  possible.
- **The vector "database" is one DuckDB file.** 24k × 384-dim vectors,
  brute-force cosine scan — single-digit milliseconds, no ANN index or vector
  service needed at this scale.
- **Real-world Excel/CSV handling**: multi-sheet workbooks, title rows before
  headers (auto-detected), bilingual descriptions, zipped StatCan bulk tables,
  multiple encodings.
- **Read-only by construction**: SQL is screened against write/DDL patterns;
  CKAN access is GET-only.
- **Refresh** the index without a full rebuild:
  `venv/bin/python semantic/build_index.py --refresh 1000` re-indexes the 1000
  most recently modified datasets.
- **Rebuilding from scratch** is optional — most users should just download the
  release asset. If you want to: `venv/bin/python semantic/build_index.py`
  (~15 min catalogue download + 10-40 min embedding on CPU). With
  `pip install torch sentence-transformers` it auto-detects Apple
  Silicon/CUDA and runs ~7x faster.

## Limitations

- Discovery covers datasets with tabular (CSV/Excel/Parquet/JSON) or
  PDF/TXT resources — ~24k of the portal's ~47k entries. Purely geospatial/HTML
  datasets are reachable via keyword search only.
- Some StatCan mirrors on the portal are terminated series; check date coverage
  (the current series usually exists under a near-identical title).
- `datastore_search_sql` is disabled on open.canada.ca, so server-side querying
  uses `q`/`filters`/`sort` rather than raw SQL.

## Observability & Anonymous Telemetry

The opendata.fyi MCP server includes lightweight, non-blocking usage telemetry
to help maintainers understand tool reliability, performance, and which public
datasets are surfaced, inspected, and queried.

### Privacy & Anonymity
- **Collected:** a temporary session ID, tool name, success/failure status,
  normalized error code, latency, server version, and an ordered list of unique
  public dataset IDs when datasets appear in search results, are opened, or are
  queried. Each tool call produces one telemetry row.
- **Not collected:** raw questions or search queries, SQL, filters, complete
  URLs, full error messages, file paths, or resource contents.
- **Anonymous discovery funnel:** the session ID groups dataset-result,
  inspection, and query events from one server run without identifying a user.
- **Non-blocking:** events dispatch asynchronously in a background thread.

### Opting Out / Disabling Telemetry
Telemetry is active by default. You can completely turn it off at any time using any of these methods:

#### Method 1: Via MCP Client Configuration (Recommended)
Add `"env": { "OPENMCP_TELEMETRY_DISABLED": "true" }` to your MCP configuration file (`claude_desktop_config.json` or `.mcp.json`):

```json
{
  "mcpServers": {
    "openmcp": {
      "command": "/absolute/path/to/openmcp/venv/bin/python",
      "args": ["/absolute/path/to/openmcp/mcp_server.py"],
      "env": {
        "OPENMCP_TELEMETRY_DISABLED": "true"
      }
    }
  }
}
```

#### Method 2: Via Local `.env` File
Create a `.env` file in the project root (or copy `.env.example`) and set:

```env
OPENMCP_TELEMETRY_DISABLED=true
```

#### Method 3: Via Environment Variable
```bash
export OPENMCP_TELEMETRY_DISABLED=true
```

## License

MIT
