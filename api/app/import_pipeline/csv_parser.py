"""Parse FantasyPros HTML or plain CSV into a DataFrame + metadata."""
from __future__ import annotations
import io
import pandas as pd


def split_name_team(combined: str) -> tuple[str, str]:
    combined = combined.strip()
    parts = combined.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isupper() and 2 <= len(parts[1]) <= 3:
        return parts[0], parts[1]
    return combined, ""


def parse_file(content: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
    """Auto-detect: HTML (FantasyPros) or plain CSV. Returns (df, meta)."""
    head = content[:256].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        tables = pd.read_html(io.BytesIO(content))
        df = max(tables, key=lambda t: t.shape[0])
        return df, {"format": "html", "filename": filename}
    df = pd.read_csv(io.BytesIO(content))
    return df, {"format": "csv", "filename": filename}
