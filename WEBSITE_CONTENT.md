# OpenMCP Canada — Website Content

This is the copy deck for a one-page marketing website. Headings, body copy,
buttons, labels, and supporting notes are separated so the content can be moved
directly into a design.

---

## Site metadata

**Page title**

OpenMCP Canada — Ask questions of Canadian open data

**Meta description**

Connect your AI assistant to 24,000+ Government of Canada datasets. Discover,
query, and cite public data in plain English with no API keys required.

**Social sharing title**

Canadian open data, ready for your AI assistant

**Social sharing description**

OpenMCP Canada helps MCP-compatible AI assistants find and query 24,000+
Government of Canada datasets—and return answers with links to the source.

---

## Navigation

- How it works
- What it can do
- Get started
- FAQ
- GitHub

**Primary navigation button:** Get OpenMCP

---

## Hero

**Eyebrow**

Open source · No API keys · Works with MCP clients

**Headline**

Ask questions of Canadian open data.

**Supporting copy**

OpenMCP Canada connects your AI assistant to 24,000+ datasets from the
Government of Canada. Find the right data, query it in place, and get an answer
with links back to the official source.

**Primary button**

Get started on GitHub

**Secondary button**

See how it works

**Supporting line below buttons**

MIT licensed. Runs locally. Compatible with Claude, ChatGPT, Codex, Cursor,
Gemini CLI, Zed, and other MCP clients.

---

## Problem statement

**Section label**

Open data should be easier to use

**Heading**

Less hunting through portals. More answers from public data.

**Body**

Canada publishes an enormous amount of useful public data, but getting from a
question to an answer often means searching unfamiliar catalogues, downloading
multiple files, decoding spreadsheets, and figuring out which resource is
current.

OpenMCP Canada gives AI assistants the tools to handle that work. You ask a
question in plain English. Your assistant finds relevant datasets, inspects
their structure, queries the useful rows, and shows you where the information
came from.

---

## How it works

**Section label**

From question to source

**Heading**

Traceable path to data.

### 1. Discover

OpenMCP combines semantic search with the Government of Canada portal’s keyword
search, so your assistant can find relevant datasets even when your wording
does not match the catalogue exactly.

### 2. Inspect

It checks the dataset’s resources, formats, fields, sheets, and date coverage
before deciding how to work with the data.

### 3. Query

Whenever possible, OpenMCP filters data on the government server. For files, it
can query CSV, Parquet, JSON, ZIP, and Excel resources and read selected pages
from PDF reports.

### 4. Cite

Results include a link back to the dataset on open.canada.ca, so you can inspect
the official source yourself.

---

## Product capabilities

**Section label**

Built for real government data

**Heading**

More than catalogue search.

**Intro**

OpenMCP handles the practical steps between discovering a dataset and using it
in an answer.

### Search by meaning

Find datasets with natural-language questions using hybrid semantic and keyword
search across a local index of 24,000+ catalogue entries.

### Query at the source

Filter datastore-backed resources on Government of Canada servers, so only the
rows you need are returned.

### Work across formats

Preview and query CSV, Parquet, JSON, ZIP, and Excel files. Inspect workbook
sheets, handle title rows, and read selected pages from PDFs.

### Avoid unnecessary downloads

OpenMCP streams remote files with DuckDB when possible and prefers server-side
queries for faster, more focused results.

### Keep the workflow read-only

Government APIs are accessed with GET requests, and file queries are screened
to prevent write and data-definition operations.

### Follow every answer back

Dataset results include links to open.canada.ca for verification, context, and
reuse.

---

## Example questions

**Section label**

What could you ask?

**Heading**

Start with a question, not a dataset name.

**Prompt cards**

- How have rental prices changed across major Canadian cities?
- Which neighbourhoods in Toronto report the worst air quality?
- How has Canada’s electricity generation mix changed over time?
- Compare population growth across provinces.
- What do federal datasets show about food price inflation?
- Find recent data on greenhouse gas emissions by sector.

**Supporting note**

The quality of an answer depends on the availability, coverage, and freshness
of the source datasets. OpenMCP helps your assistant inspect those limits rather
than hiding them.

---

## Who it is for

**Heading**

Public data for the questions you already have.

### Researchers and students

Spend less time finding and cleaning source files, and more time examining the
evidence.

### Journalists and analysts

Explore a topic quickly, compare datasets, and keep a clear trail back to the
official source.

### Developers

Add Canadian public-data discovery and querying to any MCP-compatible workflow
without building a separate data integration.

### Policy and civic teams

Use a conversational interface to investigate government data while keeping
the underlying datasets visible.

---

## Why OpenMCP

**Heading**

Local discovery. Official sources. Open standards.

### No API keys

OpenMCP uses public Government of Canada endpoints and a local embedding model.
There is no paid search service or API credential to configure.

### Runs on your machine

The semantic catalogue is a single local DuckDB file, and embeddings are
generated with a local model.

### Works with the tools you use

OpenMCP uses the standard MCP stdio protocol and can be configured in
MCP-compatible assistants and development tools.

### Open source

Inspect it, adapt it, and contribute to it. OpenMCP is available under the MIT
License.

---

## Technical callout

**Label**

Under the hood

**Heading**

A focused MCP layer over Canada’s open-data ecosystem.

**Body**

OpenMCP pairs a local DuckDB catalogue and bge-small-en-v1.5 embeddings with the
Government of Canada’s public CKAN API. Semantic and keyword results are merged
with Reciprocal Rank Fusion. Datastore resources are filtered server-side;
remote tabular files are queried with DuckDB; and PDFs are read in selected page
ranges.

**Optional stat row**

- 24,000+ indexed datasets
- 10 MCP tools
- 3 guided MCP prompts
- 0 API keys

---

## Get started

**Section label**

Open source and ready to run

**Heading**

Connect OpenMCP to your AI assistant.

**Intro**

Clone the repository, install the Python dependencies, download the latest
catalogue index, and add OpenMCP to your client’s MCP configuration.

**Step 1 label:** Install

```bash
git clone https://github.com/hsaripalli/openmcp.git
cd openmcp
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

**Step 2 label:** Download the index

Download `catalog.duckdb` from the latest GitHub release and place it in the
project root.

**Step 3 label:** Connect your MCP client

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

**Primary button**

View setup instructions

**Secondary button**

Browse the source

---

## Privacy

**Section label**

Transparent by design

**Heading**

Know what runs locally—and what gets sent.

**Body**

Search embeddings and the dataset catalogue run locally. Queries to retrieve
public data are sent to the relevant government data host.

Optional telemetry is off by default. If enabled, it records a temporary
session ID, tool name, success or failure, normalized error code, latency,
server version, and public dataset IDs that are surfaced, inspected, or
queried. It does not collect raw questions or search queries, SQL, filters,
complete URLs, full error messages, file paths, or resource contents. Set
`OPENDATA_FYI_TELEMETRY_ENABLED=true` to opt in.

**Link label**

Read the telemetry documentation

---

## FAQ

### What is OpenMCP Canada?

OpenMCP Canada is an open-source MCP server that helps AI assistants discover
and query datasets published through the Government of Canada Open Data portal.
It provides tools for search, dataset inspection, tabular queries, Excel
workbooks, and PDF reports.

### What is MCP?

The Model Context Protocol is an open standard that lets AI applications
connect to external tools and data sources. OpenMCP exposes Canadian open-data
workflows through that standard.

### Which AI clients can use it?

Any client that supports MCP servers over the standard stdio transport can use
OpenMCP. Examples include Claude, ChatGPT, Codex, Cursor, Gemini CLI, Zed,
Cline, Roo Code, Windsurf, Continue, and Goose. Setup details vary by client.

### Do I need an API key?

No. OpenMCP uses the Government of Canada’s public CKAN API, public dataset
resources, and a local embedding model.

### Does OpenMCP copy all government data to my computer?

No. The local index contains catalogue metadata and embeddings used for
discovery. OpenMCP queries source resources only when needed and prefers
server-side filtering or remote file streaming where supported.

### Is the data official?

OpenMCP searches and queries resources published through open.canada.ca and
links results back to the source dataset. OpenMCP itself is an independent
open-source project and is not an official Government of Canada service.

### What data formats are supported?

OpenMCP can work with CKAN datastore resources and remote CSV, Parquet, JSON,
ZIP, Excel, PDF, and TXT resources. Support varies with the structure and
availability of each source file.

### Does it cover every dataset on open.canada.ca?

No. Semantic discovery focuses on roughly 24,000 catalogue entries with
tabular, PDF, or text resources. Other entries, including purely geospatial or
HTML datasets, can still be found through keyword search but may require other
tools to query.

### Is it safe to query files?

OpenMCP is designed as a read-only workflow. CKAN access uses GET requests, and
SQL supplied to file-query tools is screened against write and data-definition
commands. You should still review outputs and source data before relying on
them for consequential decisions.

### What telemetry does it collect?

When enabled, opendata.fyi records a temporary session ID, tool name, success or
failure, normalized error code, latency, server version, and public dataset IDs
that are surfaced, inspected, or queried. It does not collect raw questions,
search queries, SQL, filters, complete URLs, full error messages, file paths,
or resource contents. Telemetry is off by default and can be enabled with
`OPENDATA_FYI_TELEMETRY_ENABLED=true`.

### Can I contribute?

Yes. OpenMCP is MIT licensed. Issues, feedback, and contributions are welcome
on GitHub.

---

## Final call to action

**Heading**

Turn public data into something you can ask.

**Body**

Connect OpenMCP to your AI assistant and start exploring 24,000+ Government of
Canada datasets in plain English.

**Primary button**

Get OpenMCP on GitHub

**Secondary button**

Read the documentation

---

## Footer

**Short description**

OpenMCP Canada is an independent, open-source MCP server for discovering and
querying Government of Canada open data.

**Links**

- GitHub
- Documentation
- Releases
- Report an issue
- MIT License
- open.canada.ca

**Disclaimer**

OpenMCP Canada is not affiliated with or endorsed by the Government of Canada.
Dataset content remains subject to the terms, quality, and availability of its
original publisher.

**Copyright**

© 2026 OpenMCP contributors.

---

## Link destinations

- GitHub: `https://github.com/hsaripalli/openmcp`
- Setup instructions: `https://github.com/hsaripalli/openmcp#quick-start`
- Releases / catalogue index:
  `https://github.com/hsaripalli/openmcp/releases/latest`
- Issues: `https://github.com/hsaripalli/openmcp/issues`
- License: `https://github.com/hsaripalli/openmcp/blob/main/LICENSE`
- Government of Canada Open Data:
  `https://open.canada.ca/en/open-data`

---

## Voice and terminology notes

- Use **OpenMCP Canada** on first mention and **OpenMCP** afterward.
- Lead with the user outcome: asking questions and getting traceable answers.
- Say **24,000+ indexed datasets**, not “all Canadian public data.”
- Say **Government of Canada Open Data portal**, not “Government of Canada
  database.”
- Avoid implying that OpenMCP itself generates final answers. It gives an AI
  assistant the tools and source data needed to produce them.
- Keep the independence disclaimer visible in the footer.
- Treat privacy as a factual explanation, not a blanket “private” claim:
  discovery is local, public-data requests go to source hosts, and anonymous
  telemetry is enabled by default but can be disabled.
