import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px

# --- BUSINESS LOGIC ---

class MarketingOpsEngine:
    def __init__(self):
        self.base_path = Path(__file__).parent / "data"
        self.is_live = False

    def load_local_ga4(self, report_type):
        """Attempts to load CSVs from the local /data folder."""
        file_map = {
            "traffic": "traffic.csv",
            "pages": "pages.csv",
            "events": "events.csv"
        }
        path = self.base_path / file_map.get(report_type, "")
        if path.exists():
            return pd.read_csv(path, skiprows=9)
        return None

    def audit_gtm_json(self, json_data):
        """Parses GTM JSON for lead tracking integrity."""
        workspace = json_data.get("containerVersion", {})
        tags = workspace.get("tag", [])
        inventory = []
        alerts = []
        for t in tags:
            name = t.get("name", "Unnamed")
            t_type = t.get("type", "Unknown")
            inventory.append({"Tag Name": name, "Type": t_type})
            if "GA4" in t_type and "lead" not in name.lower():
                alerts.append(f"⚠️ Naming violation: '{name}' lacks 'lead' attribution.")
        return pd.DataFrame(inventory), alerts

# --- UI SETUP ---

st.set_page_config(page_title="Leadar Ops Console", layout="wide")
engine = MarketingOpsEngine()

# --- SIDEBAR: CREDENTIALS & API ---
with st.sidebar:
    st.header("🔑 API Connectivity")
    with st.expander("Google Cloud Credentials"):
        client_id = st.text_input("Client ID", type="password")
        client_secret = st.text_input("Client Secret", type="password")
        property_id = st.text_input("GA4 Property ID (e.g. Beite.co)")
    
    if st.button("🔄 Refresh Data via API"):
        if client_id and client_secret and property_id:
            st.info("Initiating OAuth flow & API sync...")
            # API logic would be triggered here
            st.session_state["mode"] = "API"
        else:
            st.error("Missing Credentials for Live Sync.")

    st.divider()
    st.header("📂 Local Uploads")
    uploaded_gtm = st.file_uploader("Manual GTM JSON Upload", type="json")

# --- MAIN INTERFACE ---
st.title("🚀 Marketing Operations Console")
tabs = st.tabs(["Lead Analytics", "GTM Audit", "System Status"])

# 1. LEAD ANALYTICS (Prioritizes /data/ folder)
with tabs[0]:
    st.subheader("Traffic & Lead Acquisition")
    
    # Check for local data first
    df_traffic = engine.load_local_ga4("traffic")
    
    if df_traffic is not None:
        st.success("Displaying data from local storage (/data/traffic.csv)")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Total Sessions", f"{df_traffic.iloc[:, 1].sum():,.0f}")
            st.dataframe(df_traffic.iloc[:, :3], use_container_width=True)
        with col2:
            fig = px.bar(df_traffic.head(8), x=df_traffic.columns[0], y=df_traffic.columns[1], 
                         title="Top Channels", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No local traffic data found. Please sync via API or add traffic.csv to /data.")

# 2. GTM AUDIT (Works with /data/ or manual JSON upload)
with tabs[1]:
    st.subheader("GTM Configuration Audit")
    
    # Check for local JSON in /data or use the uploader
    local_gtm_path = Path(__file__).parent / "data" / "container.json"
    active_json = None
    
    if uploaded_gtm:
        active_json = json.load(uploaded_gtm)
        st.info("Using manually uploaded GTM JSON.")
    elif local_gtm_path.exists():
        with open(local_gtm_path, "r") as f:
            active_json = json.load(f)
        st.success("Loaded GTM container from /data/container.json")

    if active_json:
        inventory, alerts = engine.audit_gtm_json(active_json)
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Integrity Checks**")
            if not alerts:
                st.success("Lead tracking schema is valid.")
            else:
                for a in alerts: st.warning(a)
        with c2:
            st.write("**Tag Inventory**")
            st.dataframe(inventory, use_container_width=True)
    else:
        st.info("Upload GTM JSON or place container.json in /data to begin audit.")

# 3. SYSTEM STATUS
with tabs[2]:
    st.write(f"**Data Mode:** {'📡 API' if st.session_state.get('mode') == 'API' else '📂 Local File System'}")
    st.write(f"**Target Site:** Privacy Trust")
    st.write(f"**Environment:** Streamlit Cloud")
