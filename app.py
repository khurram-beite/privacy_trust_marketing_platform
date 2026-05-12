"""
GA4 CSV data loader.
Handles GA4 export format which has 7 comment/metadata rows before the actual headers.
"""

import pandas as pd
import io
import json
from pathlib import Path

GA4_SKIP_ROWS = 9  # GA4 exports have metadata rows before the actual header


def _load_csv(path_or_text: str, skip: int = GA4_SKIP_ROWS) -> pd.DataFrame:
    """Load a GA4-style CSV, skipping the metadata header block."""
    if "\n" in path_or_text or "," in path_or_text[:50]:
        # treat as raw text
        try:
            return pd.read_csv(io.StringIO(path_or_text), skiprows=skip)
        except Exception:
            return pd.read_csv(io.StringIO(path_or_text), skiprows=skip - 1)
    else:
        try:
            return pd.read_csv(path_or_text, skiprows=skip)
        except Exception:
            return pd.read_csv(path_or_text, skiprows=skip - 1)


def load_traffic(source=None) -> pd.DataFrame:
    """Load traffic acquisition data."""
    if source is None:
        source = Path(__file__).parent.parent.parent / "data" / "traffic.csv"
    df = _load_csv(str(source))
    df.columns = [c.strip() for c in df.columns]
    # Rename for convenience
    col_map = {
        df.columns[0]: "channel",
        df.columns[1]: "sessions",
        df.columns[2]: "engaged_sessions",
        df.columns[3]: "engagement_rate",
        df.columns[4]: "avg_engagement_time",
        df.columns[5]: "events_per_session",
        df.columns[6]: "event_count",
        df.columns[7]: "key_events",
        df.columns[8]: "key_event_rate",
    }
    df = df.rename(columns=col_map)
    df["sessions"] = pd.to_numeric(df["sessions"], errors="coerce")
    df["key_events"] = pd.to_numeric(df["key_events"], errors="coerce")
    df["engagement_rate"] = pd.to_numeric(df["engagement_rate"], errors="coerce")
    return df.dropna(subset=["sessions"])


def load_events(source=None) -> pd.DataFrame:
    """Load events data."""
    if source is None:
        source = Path(__file__).parent.parent.parent / "data" / "events.csv"
    df = _load_csv(str(source))
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        df.columns[0]: "event_name",
        df.columns[1]: "event_count",
        df.columns[2]: "total_users",
        df.columns[3]: "events_per_user",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    df["event_count"] = pd.to_numeric(df["event_count"], errors="coerce")
    return df.dropna(subset=["event_count"])


def load_pages(source=None) -> pd.DataFrame:
    """Load pages and screens data."""
    if source is None:
        source = Path(__file__).parent.parent.parent / "data" / "pages.csv"
    df = _load_csv(str(source))
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        df.columns[0]: "page_path",
        df.columns[1]: "views",
        df.columns[2]: "active_users",
        df.columns[3]: "views_per_user",
        df.columns[4]: "avg_engagement_time",
        df.columns[5]: "event_count",
        df.columns[6]: "key_events",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    df["views"] = pd.to_numeric(df["views"], errors="coerce")
    df["key_events"] = pd.to_numeric(df["key_events"], errors="coerce")
    df["active_users"] = pd.to_numeric(df["active_users"], errors="coerce")
    df["avg_engagement_time"] = pd.to_numeric(df["avg_engagement_time"], errors="coerce")
    # Filter out junk rows (blob: URIs, base64 data URIs, wp-admin)
    junk_patterns = ["blob:", "data:text", "data:application", "base64,", "cache.aspx", "wp-admin", "wp-act.php"]
    mask = ~df["page_path"].str.contains("|".join(junk_patterns), na=False)
    return df[mask].dropna(subset=["views"])


def load_gtm(source=None) -> dict:
    """Load GTM container JSON."""
    if source is None:
        source = Path(__file__).parent.parent.parent / "data" / "gtm_container.json"
    with open(source, "r") as f:
        return json.load(f)