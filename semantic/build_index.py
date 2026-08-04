import os
import gzip
import json
import argparse
import logging
import requests
import sys
from typing import Dict, Any, List, Optional, Sequence

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from .embed import embed_texts
    from .store import prune_source_records, save_datasets
except ImportError:  # Direct execution: python semantic/build_index.py
    from embed import embed_texts
    from store import prune_source_records, save_datasets
from source_registry import (
    CKAN_SOURCE_IDS,
    INDEX_SOURCE_IDS,
    get_source,
    page_url,
    qualify_dataset_id,
)
from resource_policy import is_queryable_resource, resource_format

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CATALOG_URL = "https://open.canada.ca/static/od-do-canada.jsonl.gz"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_GZ_PATH = os.path.join(LOCAL_DIR, "od-do-canada.jsonl.gz")
TABULAR_FORMATS = {"CSV", "XLSX", "XLS", "PARQUET", "JSON", "PDF", "TXT", "ZIP"}

def download_catalog() -> None:
    """Download the full government catalog dump if it doesn't already exist locally."""
    if os.path.exists(LOCAL_GZ_PATH):
        logger.info(f"Catalog archive found locally at '{LOCAL_GZ_PATH}'. Skipping download.")
        return
        
    logger.info(f"Downloading catalog archive from {CATALOG_URL}...")
    response = requests.get(CATALOG_URL, stream=True, timeout=60)
    response.raise_for_status()
    
    with open(LOCAL_GZ_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    logger.info("Download completed successfully.")

def _get_english(val: Any) -> str:
    """Safely extract English content from bilingual CKAN dicts or pipe-separated strings."""
    if not val:
        return ""
    if isinstance(val, dict):
        # Prefer English, fallback to French or whatever is first
        return val.get("en") or val.get("fr") or next(iter(val.values())) or ""
    if isinstance(val, str):
        if "|" in val:
            # Governments separate bilingual texts with ' | ' e.g., 'English | Français'
            return val.split("|")[0].strip()
        return val.strip()
    return str(val)

def _get_english_list(val: Any) -> List[str]:
    """Safely extract a list of English words from bilingual lists or dictionaries."""
    if not val:
        return []
    if isinstance(val, list):
        return [_get_english(x) for x in val if x]
    if isinstance(val, dict):
        items = val.get("en") or val.get("fr") or next(iter(val.values())) or []
        if isinstance(items, list):
            return [_get_english(x) for x in items if x]
        elif isinstance(items, str):
            return [_get_english(items)]
    return []

def process_dataset_dict(ds: Dict[str, Any], source_id: str = "canada") -> Optional[Dict[str, Any]]:
    """
    Process a parsed dataset dictionary and extract queryable metadata.
    Returns None if the dataset does not contain queryable tabular resources.
    """
    # Check resources first
    resources = ds.get("resources", [])
    if not resources or not isinstance(resources, list):
        return None
        
    # Retain only resources with a working datastore or local query path.
    extracted_resources = []
    for r in resources:
        if not is_queryable_resource(r):
            continue
        fmt = resource_format(r)
        extracted_resources.append({
            "id": r.get("id", ""),
            "name": _get_english(r.get("name")),
            "format": fmt,
            "url": r.get("url", ""),
            "datastore_active": bool(r.get("datastore_active", False))
        })
        
    if not extracted_resources:
        return None
        
    # Extract metadata fields
    native_id = ds.get("id") or ds.get("name")
    if not native_id:
        return None
        
    title = _get_english(ds.get("title_translated") or ds.get("title") or ds.get("name"))
    notes = _get_english(ds.get("notes_translated") or ds.get("notes"))
    org = _get_english((ds.get("organization") or {}).get("title_translated") or (ds.get("organization") or {}).get("title"))
    
    # Extract topic categories/keywords
    topic = _get_english(ds.get("topic_category") or ds.get("subject"))
    keywords = _get_english_list(ds.get("keywords"))
    
    metadata_modified = ds.get("metadata_modified", "")
    
    # Compose clean English document text for embedding
    text_parts = []
    if title:
        text_parts.append(title)
    if notes:
        text_parts.append(notes)
    if keywords:
        text_parts.append(f"Keywords: {', '.join(keywords)}")
    if org:
        text_parts.append(f"Publisher: {org}")
    if topic:
        text_parts.append(f"Topic: {topic}")
    doc_text = "\n\n".join(text_parts)
    
    return {
        "id": qualify_dataset_id(source_id, native_id),
        "title": title,
        "org": org,
        "notes": notes,
        "topic": topic,
        "resources": extracted_resources,
        "metadata_modified": metadata_modified,
        "source_id": source_id,
        "source_type": "ckan",
        "native_id": native_id,
        "page_url": page_url(source_id, native_id),
        "doc_text": doc_text
    }

def process_dataset_line(line: str, source_id: str = "canada") -> Optional[Dict[str, Any]]:
    """
    Parse a single line from the JSONL export and structure the dataset metadata.
    Returns None if the dataset does not contain queryable tabular resources.
    """
    try:
        ds = json.loads(line)
    except json.JSONDecodeError:
        return None
    return process_dataset_dict(ds, source_id=source_id)


def fetch_ckan_catalog(source_id: str, limit: Optional[int] = None,
                       sort: str = "metadata_modified desc") -> List[Dict[str, Any]]:
    """Fetch and normalize one registered CKAN catalog in bounded pages."""
    source = get_source(source_id)
    if source.source_type != "ckan" or not source.api_base:
        raise ValueError(f"Source '{source_id}' does not expose a CKAN Action API.")
    kept: List[Dict[str, Any]] = []
    start = 0
    page_size = min(limit or 100, 100)
    while limit is None or len(kept) < limit:
        rows = min(page_size, (limit - len(kept)) if limit else page_size)
        response = requests.get(
            f"{source.api_base}/package_search",
            params={"q": "*:*", "sort": sort, "rows": rows, "start": start},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("success"):
            raise RuntimeError(f"CKAN catalog request failed for {source_id}: {body.get('error')}")
        payload = body.get("result", {})
        raw_results = payload.get("results", [])
        if not raw_results:
            break
        for raw in raw_results:
            processed = process_dataset_dict(raw, source_id=source_id)
            if processed:
                kept.append(processed)
                if limit and len(kept) >= limit:
                    break
        start += len(raw_results)
        if start >= payload.get("count", start):
            break
    logger.info("Fetched %d queryable datasets from %s.", len(kept), source.name)
    return kept


def _code_lookup(items: Any, code_field: str, label_field: str) -> Dict[str, str]:
    """Build a string-keyed WDS code lookup from a code-set array."""
    if not isinstance(items, list):
        return {}
    return {
        str(item[code_field]): str(item[label_field])
        for item in items
        if item.get(code_field) is not None and item.get(label_field)
    }


def process_statcan_cube(cube: Dict[str, Any],
                         code_sets: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize one Statistics Canada WDS cube/table for semantic indexing."""
    product_id = str(cube.get("productId") or "").strip()
    title = str(cube.get("cubeTitleEn") or "").strip()
    if not product_id or not title:
        return None

    subject_lookup = _code_lookup(
        code_sets.get("subject"), "subjectCode", "subjectEn"
    )
    survey_lookup = _code_lookup(
        code_sets.get("survey"), "surveyCode", "surveyEn"
    )
    frequency_lookup = _code_lookup(
        code_sets.get("frequency"), "frequencyCode", "frequencyDescEn"
    )
    subject_codes = [str(value) for value in (cube.get("subjectCode") or [])]
    survey_codes = [str(value) for value in (cube.get("surveyCode") or [])]
    subjects = [subject_lookup.get(code, code) for code in subject_codes]
    surveys = [survey_lookup.get(code, code) for code in survey_codes]
    frequency = frequency_lookup.get(
        str(cube.get("frequencyCode") or ""),
        str(cube.get("frequencyCode") or ""),
    )
    is_archived = str(cube.get("archived", "")) != "2"
    status = "archived" if is_archived else "active"
    cansim_id = str(cube.get("cansimId") or "").strip()
    start_date = str(cube.get("cubeStartDate") or "")[:10]
    end_date = str(cube.get("cubeEndDate") or "")[:10]
    dimensions = [
        str(item.get("dimensionNameEn", "")).strip()
        for item in (cube.get("dimensions") or [])
        if item.get("dimensionNameEn")
    ]

    note_parts = [f"Statistics Canada table {product_id}."]
    if cansim_id:
        note_parts.append(f"Former CANSIM identifier: {cansim_id}.")
    if start_date or end_date:
        note_parts.append(f"Reference-period coverage: {start_date or '?'} to {end_date or '?'}.")
    if frequency:
        note_parts.append(f"Frequency: {frequency}.")
    note_parts.append(f"Table status: {status}.")
    if surveys:
        note_parts.append(f"Surveys/programs: {', '.join(surveys)}.")
    if dimensions:
        note_parts.append(f"Dimensions: {', '.join(dimensions)}.")
    notes = " ".join(note_parts)
    topic = "; ".join(subjects)
    keywords = [*subjects, *surveys, *dimensions, frequency, cansim_id, product_id]
    doc_text = "\n\n".join(filter(None, (
        title,
        notes,
        f"Keywords: {', '.join(value for value in keywords if value)}",
        "Publisher: Statistics Canada",
        f"Topic: {topic}" if topic else "",
    )))
    metadata = {
        **cube,
        "source": "Statistics Canada Web Data Service",
        "status": status,
        "subjectLabelsEn": subjects,
        "surveyLabelsEn": surveys,
        "frequencyLabelEn": frequency,
    }
    return {
        "id": qualify_dataset_id("statcan", product_id),
        "title": title,
        "org": "Statistics Canada",
        "notes": notes,
        "topic": topic,
        "resources": [{
            "id": f"statcan-{product_id}-eng",
            "name": "Full table (English CSV ZIP)",
            "format": "ZIP",
            "url": f"https://www150.statcan.gc.ca/n1/tbl/csv/{product_id}-eng.zip",
            "datastore_active": False,
        }],
        "metadata_modified": cube.get("releaseTime", ""),
        "source_id": "statcan",
        "source_type": "statcan_wds",
        "native_id": product_id,
        "page_url": page_url("statcan", product_id),
        "metadata": metadata,
        "doc_text": doc_text,
    }


def fetch_statcan_catalog(limit: Optional[int] = None,
                          newest_first: bool = False) -> List[Dict[str, Any]]:
    """Fetch Statistics Canada's full table metadata with two bulk calls."""
    source = get_source("statcan")
    inventory_response = requests.get(
        f"{source.api_base}/getAllCubesList", timeout=90
    )
    inventory_response.raise_for_status()
    inventory = inventory_response.json()
    codes_response = requests.get(f"{source.api_base}/getCodeSets", timeout=60)
    codes_response.raise_for_status()
    codes_body = codes_response.json()
    if not isinstance(inventory, list):
        raise RuntimeError("Statistics Canada WDS returned an invalid cube inventory.")
    if codes_body.get("status") != "SUCCESS":
        raise RuntimeError("Statistics Canada WDS returned invalid code sets.")
    if newest_first:
        inventory.sort(key=lambda item: item.get("releaseTime", ""), reverse=True)
    if limit is not None:
        inventory = inventory[:max(0, limit)]
    code_sets = codes_body.get("object", {})
    records = [
        record
        for cube in inventory
        if (record := process_statcan_cube(cube, code_sets)) is not None
    ]
    logger.info("Fetched %d table records from %s.", len(records), source.name)
    return records


def _embed_and_save(records: Sequence[Dict[str, Any]], batch_size: int = 1024) -> None:
    """Embed and upsert records in bounded batches."""
    for start in range(0, len(records), batch_size):
        batch = list(records[start:start + batch_size])
        embeddings = embed_texts([record["doc_text"] for record in batch], is_query=False)
        for record, embedding in zip(batch, embeddings):
            record["embedding"] = embedding
        save_datasets(batch)
        logger.info("Indexed %d/%d records.", min(start + len(batch), len(records)), len(records))

def refresh_index(count: int, sources: Optional[Sequence[str]] = None) -> None:
    """
    Incrementally refresh the index by fetching recently modified packages from CKAN API.
    Does not require downloading the full catalogue dump.
    """
    selected = list(sources or INDEX_SOURCE_IDS)
    processed_datasets: List[Dict[str, Any]] = []
    for source_id in selected:
        if source_id == "statcan":
            processed_datasets.extend(
                fetch_statcan_catalog(limit=count, newest_first=True)
            )
        else:
            processed_datasets.extend(fetch_ckan_catalog(source_id, limit=count))
    if processed_datasets:
        _embed_and_save(processed_datasets)
    logger.info("Incremental refresh completed.")

def build_index(limit: Optional[int] = None,
                sources: Optional[Sequence[str]] = None) -> None:
    """Read local archive, stream & parse records, embed them, and save to DuckDB."""
    selected = list(sources or INDEX_SOURCE_IDS)
    processed_datasets = []
    if "canada" in selected:
        download_catalog()
        total_lines = 0
        with gzip.open(LOCAL_GZ_PATH, "rt", encoding="utf-8") as handle:
            for line in handle:
                total_lines += 1
                ds_data = process_dataset_line(line, source_id="canada")
                if ds_data:
                    processed_datasets.append(ds_data)
                if limit and len(processed_datasets) >= limit:
                    break
        logger.info("Parsed %d federal records; kept %d.", total_lines,
                    len(processed_datasets))
    for source_id in selected:
        if source_id in ("canada", "statcan"):
            continue
        processed_datasets.extend(fetch_ckan_catalog(source_id, limit=limit))
    if "statcan" in selected:
        processed_datasets.extend(fetch_statcan_catalog(limit=limit))
    if not processed_datasets:
        logger.warning("No datasets match the tabular filter criteria.")
        return
    _embed_and_save(processed_datasets)
    if limit is None:
        for source_id in selected:
            keep_ids = [
                record["id"] for record in processed_datasets
                if record["source_id"] == source_id
            ]
            prune_source_records(source_id, keep_ids)
    logger.info("Catalog indexing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build or refresh semantic search index over government datasets.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of datasets to index (for faster testing).")
    parser.add_argument("--refresh", type=int, default=None, help="Incrementally refresh index with the specified number of recently modified datasets.")
    parser.add_argument(
        "--sources", nargs="+", choices=INDEX_SOURCE_IDS,
        default=list(INDEX_SOURCE_IDS),
        help="Catalog sources to index (default: all registered sources).",
    )
    args = parser.parse_args()
    
    if args.refresh is not None:
        refresh_index(args.refresh, sources=args.sources)
    else:
        build_index(limit=args.limit, sources=args.sources)
