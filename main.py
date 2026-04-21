"""
NAICS Lookup API
Searches 2022 6-digit NAICS codes by title and description, returning top 5 matches.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from pydantic import BaseModel
from typing import Optional
import openpyxl
import re
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)
DATA_PATH = os.getenv("NAICS_DATA_PATH", "data/2022 NAICS Codes.xlsx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.naics_data = load_naics(DATA_PATH)
        logger.info("Loaded %d NAICS records from %s", len(app.state.naics_data), DATA_PATH)
    except FileNotFoundError:
        logger.error("NAICS data file not found: %s", DATA_PATH)
        app.state.naics_data = []
    except Exception as exc:
        logger.exception("Failed to load NAICS data: %s", exc)
        app.state.naics_data = []
    yield


app = FastAPI(
    title="NAICS Lookup API",
    description="Search 2022 6-digit NAICS codes by keyword. Returns top 5 best matches.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_naics(path: str = "data/2022 NAICS Codes.xlsx") -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Six Digit NAICS"]
    records = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # skip header
        try:
            _, code, title, description = row[0], row[1], row[2], row[3]
        except (IndexError, ValueError):
            logger.warning("Skipping malformed row %d: %s", i, row)
            continue
        if not code or not title:
            continue
        try:
            code_str = str(int(code))
        except (TypeError, ValueError):
            logger.warning("Skipping row %d with non-numeric code: %r", i, code)
            continue
        records.append({
            "code": code_str,
            "title": title or "",
            "description": description or "",
            "_title_tokens": set(tokenize(title or "")),
            "_desc_tokens":  set(tokenize(description or "")),
        })
    wb.close()
    return records


def tokenize(text: str) -> list[str]:
    """Lower-case, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_naics_data(request: Request) -> list[dict]:
    data = request.app.state.naics_data
    if not data:
        raise HTTPException(status_code=503, detail="NAICS data unavailable. Check server logs.")
    return data


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

TITLE_EXACT_WEIGHT   = 100   # query phrase found verbatim in title
DESC_EXACT_WEIGHT    = 60    # query phrase found verbatim in description
TITLE_WORD_WEIGHT    = 15    # each query word found in title
DESC_WORD_WEIGHT     = 5     # each query word found in description
FUZZY_TITLE_WEIGHT   = 0.4   # rapidfuzz partial_ratio on title (scaled 0-40)
FUZZY_DESC_WEIGHT    = 0.15  # rapidfuzz partial_ratio on description (scaled 0-15)


def score(q_lower: str, q_tokens: set, record: dict) -> float:
    title_lc = record["title"].lower()
    desc_lc  = record["description"].lower()

    s = 0.0

    # Exact phrase hits
    if q_lower in title_lc:
        s += TITLE_EXACT_WEIGHT
    if q_lower in desc_lc:
        s += DESC_EXACT_WEIGHT

    # Individual word hits
    s += len(q_tokens & record["_title_tokens"]) * TITLE_WORD_WEIGHT
    s += len(q_tokens & record["_desc_tokens"])  * DESC_WORD_WEIGHT

    # Fuzzy similarity (handles typos / partial matches)
    s += fuzz.partial_ratio(q_lower, title_lc) * FUZZY_TITLE_WEIGHT
    s += fuzz.partial_ratio(q_lower, desc_lc)  * FUZZY_DESC_WEIGHT

    return s


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class NAICSResult(BaseModel):
    code: str
    title: str
    description: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: list[NAICSResult]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/search", response_model=SearchResponse, summary="Search NAICS codes")
def search(
    q: str = Query(..., min_length=3, max_length=200, description="Search query (business type, activity, keywords)"),
    include_description: bool = Query(False, description="Include full description text in results"),
    limit: int = Query(5, ge=1, le=20, description="Number of results to return (default 5, max 20)"),
    naics_data: list[dict] = Depends(get_naics_data),
):
    """
    Search 2022 6-digit NAICS codes by title and description.
    Returns up to `limit` best matches ranked by relevance.
    """
    q_lower  = q.lower()
    q_tokens = set(tokenize(q))

    scored = [(score(q_lower, q_tokens, r), r) for r in naics_data]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    results = [
        NAICSResult(
            code=r["code"],
            title=r["title"],
            description=r["description"] if include_description else None,
            score=round(s, 2),
        )
        for s, r in top
    ]

    return SearchResponse(query=q, results=results)


@app.get("/code/{naics_code}", response_model=NAICSResult, summary="Look up a specific NAICS code")
def get_by_code(
    naics_code: str = Path(..., pattern=r"^\d{6}$", description="6-digit NAICS code"),
    naics_data: list[dict] = Depends(get_naics_data),
):
    """
    Return the title and description for an exact 6-digit NAICS code.
    """
    for r in naics_data:
        if r["code"] == naics_code:
            return NAICSResult(
                code=r["code"],
                title=r["title"],
                description=r["description"],
            )
    raise HTTPException(status_code=404, detail=f"NAICS code {naics_code} not found.")


@app.get("/health")
def health(request: Request):
    data = request.app.state.naics_data
    return {"status": "ok" if data else "degraded", "records_loaded": len(data)}
