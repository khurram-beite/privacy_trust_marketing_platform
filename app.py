import streamlit as st
import pandas as pd
import io
import json
from pathlib import Path
import traceback

# --- CONFIGURATION ---
st.set_page_config(page_title="Leadar GA4 Dashboard", layout="wide")
GA4_SKIP_ROWS = 9 

# --- DATA LOADING LOGIC ---

def _load_csv(path_or_text: str, skip: int = GA4_SKIP_ROWS) -> pd.DataFrame:
    """Load a GA4-style CSV, skipping the metadata header block."""
    try:
        # Check if it's a path or raw string
        if isinstance(path_or_text, str) and ("\n" in path_or_text or "," in path_or_text[:50]):
            content = io.StringIO(path_or_text)
        else:
            content = path_or_text

        return pd.read_csv(content, skiprows=skip)
    except Exception:
        # Fallback for slightly different GA4 export formats
        if isinstance(path_or_text, str) and ("\n" in path_or_text or "," in path_or_text[:50]):
            content = io.StringIO(path_or_text)
        else:
            content = path_or_text
        return pd.read_csv(content, skiprows=skip - 1)

def load_traffic(source) -> pd.DataFrame:
    df = _load_csv(source)
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        df.columns[0]: "channel",
        df.columns[1]: "sessions",
        df.columns[2]: "engaged_sessions",
        df.columns[8]: "key_event_rate",
    }
    df = df.rename(columns=col_map)
    for col in ["sessions", "key_event_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["sessions"])

def load_pages(source) -> pd.DataFrame:
    df = _load_csv(source)
    df.columns = [c.strip() for c in df.columns]
    col_map = {
        df.columns[0]: "page_path",
        df.columns[1]: "views",
        df.columns[2]: "active_users",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    df["views"] = pd.to_numeric(df["views"], errors="coerce")
    
    # Filter out WordPress admin/junk paths for leadar.digital cleanup
    junk_patterns = ["wp-admin", "wp-act.php", "blob:", "base64"]
    mask = ~df["page_path"].str.contains("|".join(junk_patterns), na=False)
    return df[mask].dropna(subset=["views"])

# --- STREAMLIT UI ---

st.title("📊 GA4 Data Explorer")
st.sidebar.header("Data Sources")

# Path configuration (Relative to current script)
base_path = Path(__file__).parent.parent.parent / "data"
traffic_path = base_path / "traffic.csv"
pages_path = base_path / "pages.csv"

tabs = st.tabs(["Traffic Overview", "Page Performance", "Debug/Raw Data"])

# --- TAB 1: TRAFFIC ---
with tabs[0]:
    st.subheader("Traffic Acquisition")
    if traffic_path.exists():
        try:
            df_traffic = load_traffic(str(traffic_path))
            
            # Quick Metrics
            total_sessions = df_traffic["sessions"].sum()
            st.metric("Total Sessions", f"{total_sessions:,.0f}")
            
            # Table
            st.dataframe(df_traffic, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading traffic.csv: {e}")
    else:
        st.warning(f"Traffic file not found at: {traffic_path}")

# --- TAB 2: PAGES ---
with tabs[1]:
    st.subheader("Page Views & Active Users")
    if pages_path.exists():
        try:
            df_pages = load_pages(str(pages_path))
            st.bar_chart(df_pages.set_index("page_path")["views"].head(10))
            st.dataframe(df_pages, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading pages.csv: {e}")
    else:
        st.warning(f"Pages file not found at: {pages_path}")

# --- TAB 3: DEBUG ---
with tabs[2]:
    st.subheader("System Troubleshooting")
    st.write("**Current Directory:**", Path.cwd())
    st.write("**Expected Data Path:**", base_path.absolute())
    
    if st.button("Show Full Error Traceback"):
        st.code(traceback.format_exc())
