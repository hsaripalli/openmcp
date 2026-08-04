# Roadmap (local notes — not published)

## Done

- [x] P1 — Government-host download reliability
      Browser-ish User-Agent on all requests, broadened transient-error
      retry set (ConnectionError, SSLError, ChunkedEncodingError), TLS 1.2
      fallback session, and a local-download fallback for the non-ZIP
      `query_remote_file` path when DuckDB httpfs itself gets reset
      (httpfs has no UA / no TLS pin of its own).

- [x] P1b — Structured core-tool outputs and query isolation
      `semantic_search_datasets`, `get_dataset`, `query_datastore`, and
      `query_remote_file` now publish one MCP output schema while preserving a
      Markdown compatibility response. Errors carry stable codes and recovery
      guidance; query results carry rows, columns, sources, and a reproducible
      query description. DuckDB queries use isolated per-call connections with
      active interruption on timeout. Reliability tests cover the contract,
      citations, limits, SQL validation, telemetry, and connection lifecycle.

## P2a — Non-CKAN source catalogs — Done

Statistics Canada publishes a complete non-CKAN table inventory through its
Web Data Service, so it is handled as a first-class bulk metadata source.

Implemented:
- Statistics Canada is a complete first-class catalog adapter. One
  `getAllCubesList` call harvests every table and its published metadata, while
  `getCodeSets` resolves subjects, surveys, and frequencies. No tables are
  selected by hand.
- Each StatCan record retains its raw WDS metadata and gets authoritative table
  and full-table CSV URLs before embedding.

## P2b — Multi-portal CKAN adapter — Done

The Government of Alberta and Ontario data catalogues expose CKAN Action APIs,
so they should reuse the existing discovery and file-query pipeline rather than
being treated as Socrata sources.

Implemented:
- Replaced the hardcoded `CKAN_BASE` with a source registry containing the
  portal name, API base URL, public dataset-page template, and language rules.
- Added `open.alberta.ca` and `data.ontario.ca`, with source-qualified IDs
  so records cannot collide across catalogues.
- Each catalogue can be ingested into the shared semantic index; `source_type`,
  `source_id`, `native_id`, and `page_url` are included in every record.
- Live keyword search is bounded, concurrent, and failure-isolated across portals.
- Ordinary resources continue through `query_remote_file`; `query_datastore`
  is routed only to the CKAN portal that owns the resource.

## P2c — `query_socrata` connector

Several municipalities, including Calgary, publish through Socrata, which
supports server-side SoQL
aggregation (`$select`, `$where`, `$group`, `$order`) — the same
"filter/aggregate server-side, don't download" philosophy as
`query_datastore` for CKAN.

Plan:
- `query_socrata(domain, dataset_id, select="", where="", group="",
  order="", limit=50)` — builds a SoQL query against
  `https://{domain}/resource/{dataset_id}.json`.
- Small allowlisted registry of verified Socrata domains (starting with
  `data.calgary.ca`) so discovery can suggest it.
- Bigger scope than P2a: this is a new query surface with its own
  discovery problem (which datasets exist on which domain?) — treat as a
  v1.1 feature, not a patch. Needs its own design pass before starting.



10x performance: 

The core opportunity is to turn it from “a collection of data-reading tools” into a public-data research engine.

Today, the assistant may need several calls:

```text
Search → inspect dataset → choose resource → inspect schema
→ formulate query → retrieve rows → retry → cite
```

The 10× version would feel more like:

```text
Question → evidence bundle → answer or artifact
```

## Highest-leverage ideas

| Idea | Why it matters |
|---|---|
| One-call research tool | Reduces six or more tool calls to one coordinated workflow |
| Structured outputs | Makes results easier and cheaper for any LLM to understand |
| Intelligent resource selection | Stops the assistant from guessing which CSV, table or workbook to use |
| Better ranking | Gets the right dataset into the top three more consistently |
| Caching and concurrency | Makes repeated work dramatically faster |
| Provenance bundles | Makes every result reproducible and trustworthy |
| Automatic catalogue updates | Removes manual index downloads and stale metadata |
| Additional source adapters | Expands beyond one CKAN catalogue without rewriting the server |

### 1. Add a single research tool

Something like:

```text
research_public_data(
  question,
  max_datasets=3,
  max_rows=100,
  date_range=None,
  geography=None
)
```

It would:

1. Search the catalogue.
2. Rerank the candidates.
3. Inspect the strongest datasets.
4. Choose the best resource from each.
5. Inspect the schema.
6. Retrieve targeted evidence.
7. Return citations and a reproducible query manifest.

It should not write the final narrative. The user’s chosen AI assistant can still create the answer, chart or report.

This would make the server much more consistent across ChatGPT, Claude, Codex, Cursor and other clients.

### 2. Return structured data instead of primarily Markdown

Every tool should return a predictable object:

```json
{
  "datasets": [],
  "columns": [],
  "rows": [],
  "sources": [],
  "query": {},
  "warnings": []
}
```

MCP supports `outputSchema`, `structuredContent`, tool errors and resource links. You can preserve Markdown as a compatibility fallback. [MCP tool specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

This would:

- Reduce parsing mistakes
- Reduce tokens
- Make citations easier to preserve
- Let clients build tables and visualizations directly
- Make automated testing much easier

This structured-output foundation is now implemented for the four core tools.
The remaining tools can migrate to the same contract incrementally.

### 3. Build a resource-selection engine

A dataset may contain dozens of resources: old editions, bilingual copies, documentation, ZIP archives and multiple formats.

Instead of returning everything, score each resource using:

- Datastore availability
- Format
- Language
- Recency
- Date coverage
- File size
- Schema relevance
- Whether it is documentation or actual data
- Whether the series appears current or discontinued

Then return:

```text
Recommended resource
Alternative resource
Reason for selection
Known limitations
```

This would eliminate many failed or wasteful tool calls.

### 4. Improve retrieval quality

The existing semantic + keyword + RRF approach is a strong baseline. The next level would be:

- Multilingual embeddings for English and French
- A small local reranker over the top 25–50 results
- Query expansion for acronyms and Canadian terminology
- Freshness, queryability and source-quality signals
- Separate weighting for title, description, tags, publisher and fields
- Geographic and temporal intent detection

The goal should be “right dataset in the top three,” not merely “related dataset somewhere in the top ten.”

### 5. Add an evaluation benchmark

Create 100–200 representative questions with:

- Expected relevant dataset IDs
- Expected top resource
- Expected fields
- A query that should succeed
- Required source links

Track:

- Recall@3
- Top-resource accuracy
- Successful-query rate
- Median tool calls per question
- Time to first useful row
- Response tokens
- Citation completeness

This gives you a way to prove that each change improves the server rather than merely making it more complicated.

### 6. Cache aggressively and run independent work concurrently

Useful caches include:

- Search results
- `package_show` responses
- Resource-to-dataset mappings
- Schemas
- Excel sheet metadata
- HTTP `ETag` and `Last-Modified` values
- Small downloaded resources
- Query results with short TTLs

The local semantic search and live CKAN search should run concurrently. Resource inspections for the top candidates can also run concurrently.

Be careful with the shared DuckDB connection: DuckDB recommends separate connections for parallel Python work rather than sharing one connection across threads. [DuckDB concurrency guidance](https://duckdb.org/docs/stable/clients/python/overview)

### 7. Return artifact-ready resources

Large results should not be pasted into the LLM context as enormous Markdown tables.

Return:

- A small structured preview inline
- Full results as a temporary CSV, Parquet or Arrow resource
- A resource link the client can fetch when needed
- A compact provenance manifest alongside it

DuckDB already supports efficient Arrow conversion, while Parquet supports projection and filter pushdown so only relevant columns and row groups are read. [DuckDB Parquet documentation](https://duckdb.org/docs/stable/data/parquet/overview)

### 8. Make every result reproducible

For each retrieval, return an evidence manifest:

```json
{
  "dataset_id": "...",
  "resource_id": "...",
  "source_url": "...",
  "retrieved_at": "...",
  "source_modified_at": "...",
  "columns_selected": [],
  "filters": {},
  "sql": "...",
  "rows_returned": 42
}
```

Then add:

```text
replay_query(manifest)
```

This would strengthen the “traceable path to the data” promise considerably.

### 9. Automate catalogue freshness

Users should not need to manually download a new 120 MB index.

The server could:

- Check the local index version on startup
- Download only when a newer release exists
- Refresh changed catalogue records incrementally
- Remove withdrawn datasets
- Store the index build date and source revision
- Warn when the index is stale

This is both an effectiveness and an adoption improvement.

### 10. Create a source-adapter interface

Define a common internal contract:

```text
search()
get_dataset()
list_resources()
inspect()
query()
cite()
```

Then implement adapters for:

- CKAN
- Statistics Canada APIs
- ArcGIS FeatureServer
- Socrata
- Municipal open-data portals
- OGC/geospatial services

That would let opendata.fyi expand sources without turning the server into a large set of special cases.

## What I would build first

1. Structured tool outputs and proper error objects  
2. Resource ranking and automatic selection  
3. A measurable evaluation benchmark  
4. Parallel search plus schema/package caching  
5. A one-call research/evidence tool  
6. Automatic index updates  
7. Additional source adapters  
8. Geography, time and cross-dataset joins  

I would not prioritize more file formats, a larger vector database or server-generated prose yet. The real 10× improvement is reliably getting from a question to a small, structured, source-linked evidence bundle with fewer calls.

# Geofiles 

Absolutely. Geospatial data should be a first-class execution path—not squeezed into `query_remote_file`.

The server could classify every resource into:

```text
Tabular  → rows and columns
Vector   → points, lines and polygons
Raster   → pixels, bands and coverage
Service  → ArcGIS, OGC Features, WMS or tiles
Document → PDF and text
```

## Vector data

Start with:

- GeoJSON
- GeoParquet
- Shapefile ZIPs
- GeoPackage
- FlatGeobuf
- KML
- ArcGIS FeatureServer
- OGC API Features and WFS

DuckDB’s spatial extension already provides geometry operations, coordinate transformations and GDAL-backed reading for formats such as Shapefile, GeoJSON and GeoPackage. [DuckDB Spatial](https://duckdb.org/docs/stable/core_extensions/spatial/functions)

Useful tools:

```text
inspect_spatial_resource(url)
list_spatial_layers(url)
query_spatial_features(url, bbox, filters, columns, limit)
spatial_join(left, right, predicate)
buffer_and_intersect(...)
```

`inspect_spatial_resource` should return:

- Coordinate reference system
- Geometry type
- Bounding box
- Feature count
- Available layers
- Attribute columns
- Time coverage
- Recommended query path

## Raster data

Treat raster as a separate system using GDAL or Rasterio rather than forcing it through ordinary DuckDB queries.

Start with:

- Cloud Optimized GeoTIFF
- GeoTIFF
- NetCDF for climate data
- Zarr for large multidimensional datasets
- STAC catalogues for discovering imagery

Useful tools:

```text
inspect_raster(url)
sample_raster(url, points)
summarize_raster(url, bbox, band)
zonal_statistics(raster, polygons)
crop_raster(url, bbox)
```

Cloud Optimized GeoTIFF should be the preferred remote format because it allows targeted HTTP reads instead of downloading the entire image. [GDAL COG documentation](https://gdal.org/en/stable/drivers/raster/cog.html)

## Map services

Add adapters for:

- ArcGIS REST services
- OGC API Features
- OGC API Tiles
- WMS
- WFS
- WMTS

These need different routing:

```text
Feature service → query actual geometries and attributes
Map service     → request a rendered image
Tile service    → return map tiles or a map configuration
Coverage service → query raster values
```

OGC now recommends its newer REST-oriented APIs where available, while many public portals still expose WMS, WFS and WMTS. [OGC standards](https://www.ogc.org/standards/)

## Map-ready outputs

Avoid placing thousands of coordinates into the LLM context. Return:

- A small feature preview
- Summary statistics
- Bounding box
- Simplified sample geometry
- Full result as GeoJSON or GeoParquet
- A resource link to the generated file
- A MapLibre-compatible layer specification
- Dataset and query provenance

GeoParquet would be particularly useful for larger results because it combines Parquet’s columnar efficiency with standardized geometry metadata. [GeoParquet specification](https://geoparquet.org/releases/v1.1.0/)

## Spatial intelligence

The server should understand spatial intent:

- “within 10 kilometres”
- “inside this watershed”
- “closest monitoring station”
- “by census subdivision”
- “intersecting wildfire zones”
- “average rainfall within each municipality”
- “change between 2015 and 2025”

That enables workflows such as:

```text
Question
  ↓
Find municipal boundaries
  ↓
Find air-quality stations
  ↓
Normalize coordinate systems
  ↓
Spatially join stations to municipalities
  ↓
Aggregate readings
  ↓
Return table + map layer + sources
```

## Essential safeguards

Geospatial resources can be enormous. Add:

- Bounding-box or polygon requirement for large resources
- Maximum feature and vertex counts
- Geometry simplification
- Raster pixel and resolution limits
- ZIP decompression limits
- CRS detection and explicit reprojection
- Source and output CRS in every response
- Local caching for metadata and small derived files
- Timeouts and memory limits

My implementation order would be:

1. Spatial resource detection and metadata inspection  
2. GeoJSON, GeoParquet, GeoPackage and zipped Shapefile querying  
3. ArcGIS FeatureServer support  
4. Bounding-box filters and spatial joins  
5. Cloud Optimized GeoTIFF inspection and sampling  
6. Zonal statistics  
7. Map-ready GeoJSON/GeoParquet outputs  
8. OGC services, STAC, NetCDF and Zarr  

This would unlock an entirely new class of questions rather than merely adding more file extensions.
