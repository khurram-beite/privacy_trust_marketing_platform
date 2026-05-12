import streamlit as st
import pandas as pd
import json
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta

# --- BUSINESS LOGIC ---

class GTMExplorer:
    def __init__(self, data):
        self.workspace = data.get("containerVersion", {})
        self.tags = self.workspace.get("tag", [])
    
    def get_tag_details(self, tag_name):
        tag = next((t for t in self.tags if t['name'] == tag_name), None)
        if not tag: return None
        params = {p['key']: p['value'] for p in tag.get('parameter', [])}
        return {
            "Name": tag.get("name"),
            "Type": tag.get("type"),
            "Measurement ID": params.get("measurementId", "N/A"),
            "Event Name": params.get("eventName", "N/A"),
            "Live": not tag.get("paused", False)
        }

# --- UI SETUP ---
st.set_page_config(page_title="Leadar Ops Console", layout="wide")
data_path = Path(__file__).parent / "data"

# 1. SIDEBAR: PERSISTENT CONFIGURATION & CREDENTIALS
with st.sidebar:
    st.header("🔑 API Connectivity")
    with st.expander("Google Cloud Credentials", expanded=True):
        client_id = st.text_input("Client ID", type="password")
        client_secret = st.text_input("Client Secret", type="password")
        property_id = st.text_input("GA4 Property ID", placeholder="e.g. 123456789")
    
    if st.button("🔄 Sync Live API"):
        if client_id and client_secret:
            st.session_state["api_active"] = True
            st.success("API Linked")
        else:
            st.error("Missing Credentials")

    st.divider()
    st.header("📂 Local GTM Upload")
    uploaded_json = st.file_uploader("Override container.json", type="json")
    st.info("Upload a JSON to audit a different workspace without changing /data/.")

# 2. MAIN CONSOLE
st.title("🚀 Marketing Operations Console")
tabs = st.tabs(["📈 Lead Analytics", "🏷️ GTM Explorer", "⚙️ System Status"])

# --- TAB 1: LEAD ANALYTICS ---
with tabs[0]:
    # LOAD DATA
    df_traffic_raw = pd.read_csv(data_path / "traffic.csv", skiprows=9) if (data_path / "traffic.csv").exists() else None
    
    if df_traffic_raw is not None:
        # --- NEW: BODY-LEVEL FILTER BAR ---
        with st.container(border=True):
            f1, f2 = st.columns([1, 2])
            with f1:
                # Mock date picker (GA4 CSVs are static, but this prepares the UI)
                date_range = st.date_input("Analysis Period", [datetime.now() - timedelta(days=30), datetime.now()])
            with f2:
                channels = df_traffic_raw.iloc[:, 0].unique().tolist()
                selected_channels = st.multiselect("Traffic Channels", channels, default=channels)

        # Apply Filters
        mask = df_traffic_raw.iloc[:, 0].isin(selected_channels)
        df_traffic = df_traffic_raw[mask]

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sessions", f"{df_traffic.iloc[:, 1].sum():,.0f}")
        m2.metric("Engagement %", f"{df_traffic.iloc[:, 3].mean():.2%}")
        m3.metric("Key Events", f"{df_traffic.iloc[:, 7].sum():,.0f}")
        m4.metric("Avg. Time", f"{df_traffic.iloc[:, 4].mean():.1f}s")

        # Visuals
        c1, c2 = st.columns(2)
        with c1:
            fig_traffic = px.pie(df_traffic, values=df_traffic.columns[1], names=df_traffic.columns[0], 
                                 title="Traffic Composition", hole=0.4, color_discrete_sequence=px.colors.qualitative.Safe)
            st.plotly_chart(fig_traffic, use_container_width=True)
        
        with c2:
            df_pages = pd.read_csv(data_path / "pages.csv", skiprows=9) if (data_path / "pages.csv").exists() else None
            if df_pages is not None:
                fig_pages = px.bar(df_pages.head(10), x=df_pages.columns[1], y=df_pages.columns[0], 
                                   orientation='h', title="Top Content Performance", color_discrete_sequence=['#1abc9c'])
                st.plotly_chart(fig_pages, use_container_width=True)

        st.subheader("Event Volume Trend")
        df_events = pd.read_csv(data_path / "events.csv", skiprows=9) if (data_path / "events.csv").exists() else None
        if df_events is not None:
            fig_events = px.line(df_events.head(10), x=df_events.columns[0], y=df_events.columns[1], 
                                 markers=True, title="Event Distribution", color_discrete_sequence=['#e67e22'])
            st.plotly_chart(fig_events, use_container_width=True)
    else:
        st.warning("Awaiting local CSV data in /data/ folder.")

# --- TAB 2: GTM EXPLORER ---
with tabs[1]:
    st.subheader("GTM Workspace Inspector")
    gtm_data = None
    if uploaded_json:
        gtm_data = json.load(uploaded_json)
    elif (data_path / "container.json").exists():
        with open(data_path / "container.json", "r") as f:
            gtm_data = json.load(f)

    if gtm_data:
        explorer = GTMExplorer(gtm_data)
        tag_names = [t['name'] for t in explorer.tags]
        
        selected_tag = st.selectbox("Search & Inspect Tag", ["Select a tag..."] + tag_names)
        
        if selected_tag != "Select a tag...":
            details = explorer.get_tag_details(selected_tag)
            with st.container(border=True):
                ca, cb, cc = st.columns(3)
                ca.write(f"**Type:** {details['Type']}")
                cb.write(f"**GA4 ID:** `{details['Measurement ID']}`")
                cc.write(f"**Status:** {'🟢 Active' if details['Live'] else '⚪ Paused'}")
                st.write(f"**Triggering on Event:** `{details['Event Name']}`")
                
                # API Sync Trigger
                if st.session_state.get("api_active"):
                    if st.button(f"✏️ Update {selected_tag} in GTM"):
                        st.info("API Bridge: Ready to push changes...")

        st.divider()
        st.dataframe(pd.DataFrame([{"Tag": t['name'], "Type": t['type']} for t in explorer.tags]), use_container_width=True)
