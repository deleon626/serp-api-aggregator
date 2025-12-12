"""Debug output utilities for CLI."""

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import SearchResult

DEBUG_DIR = Path("./debug")


@dataclass
class DebugConfig:
    """Debug flag configuration."""
    json: bool = False
    csv: bool = False
    raw: bool = False

    @property
    def any_enabled(self) -> bool:
        return self.json or self.csv or self.raw


def slugify_query(query: str, max_length: int = 50) -> str:
    """Convert query to filesystem-safe slug."""
    slug = query.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:max_length].rstrip('-')


def generate_timestamp() -> str:
    """Generate timestamp string for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_debug_dir() -> Path:
    """Create debug directory if it doesn't exist."""
    DEBUG_DIR.mkdir(exist_ok=True)
    return DEBUG_DIR


def save_debug_json(result: "SearchResult", query: str) -> Path:
    """Save full SearchResult as JSON."""
    ensure_debug_dir()
    slug = slugify_query(query)
    ts = generate_timestamp()
    path = DEBUG_DIR / f"{slug}_{ts}_json.json"
    path.write_text(result.model_dump_json(indent=2))
    return path


def save_debug_csv(result: "SearchResult", query: str) -> Path:
    """Save organic results as CSV."""
    ensure_debug_dir()
    slug = slugify_query(query)
    ts = generate_timestamp()
    path = DEBUG_DIR / f"{slug}_{ts}_csv.csv"

    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'link', 'title', 'description', 'best_position',
            'avg_position', 'frequency', 'pages_seen'
        ])
        writer.writeheader()
        for item in result.organic:
            writer.writerow({
                'link': str(item.link),
                'title': item.title,
                'description': item.description or '',
                'best_position': item.best_position,
                'avg_position': item.avg_position,
                'frequency': item.frequency,
                'pages_seen': ','.join(map(str, item.pages_seen)),
            })
    return path


def save_debug_raw(raw_responses: list[dict], query: str) -> Path:
    """Save raw API responses as NDJSON."""
    ensure_debug_dir()
    slug = slugify_query(query)
    ts = generate_timestamp()
    path = DEBUG_DIR / f"{slug}_{ts}_raw.ndjson"

    with path.open('w') as f:
        for response in raw_responses:
            f.write(json.dumps(response) + '\n')
    return path
