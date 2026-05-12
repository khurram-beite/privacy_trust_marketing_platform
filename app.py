import streamlit as st
import pandas as pd
import json
import plotly.express as px
from pathlib import Path

# --- BUSINESS LOGIC: GTM INTELLIGENCE ---

class GTMExplorer:
    def __init__(self, data):
        self.raw_data = data
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

# 1. SIDEBAR: CREDENTIALS & FILTERS
with st.sidebar:
    st.header("🔑 API Connectivity")
    with st.expander("Google Cloud Credentials", expanded=False):
        client_id = st.text_input("Client ID", type="password")
        client_secret = st.text_input("Client Secret", type="password")
        property_id = st.text_input("GA4 Property ID", placeholder="e.g. 123456789")
    
    if st.button("🔄 Refresh & Sync Live"):
        if client_id and client_secret:
            st.session_state["api_active"] = True
            st.success("API Mode Activated")
        else:
            st.error("Enter Credentials to Sync")

    st.divider()
    st.header("📂 Local Data & Uploads")
    uploaded_json = st.file_uploader("Upload GTM JSON (Manual Override)", type="json")
    
    # Analysis Filters
    st.header("🎯 Analytics Filters")
    data_path = Path(__file__).parent / "data"
    df_traffic_raw = pd.read_csv(data_path / "traffic.csv", skiprows=9) if (data_path / "traffic.csv").exists() else None
    
    selected_channels = []
    if df_traffic_raw is not None:
        channels = df_traffic_raw.iloc[:, 0].unique().tolist()
        selected_channels = st.multiselect("Traffic Channels", channels, default=channels)

# 2. MAIN CONSOLE
st.title("🚀 Marketing Operations Console")
tabs = st.tabs(["📈 Lead Analytics", "🏷️ GTM Explorer", "⚙️ System Configuration"])

# --- TAB 1: ANALYTICS (Traffic, Pages, Events) ---
with tabs[0]:
    if df_traffic_raw is not None:
        # Filtering logic
        mask = df_traffic_raw.iloc[:, 0].isin(selected_channels)
        df_traffic = df_traffic_raw[mask]

        # Metric Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sessions", f"{df_traffic.iloc[:, 1].sum():,.0f}")
        m2.metric("Engagement Rate", f"{df_traffic.iloc[:, 3].mean():.2%}")
        m3.metric("Key Events", f"{df_traffic.iloc[:, 7].sum():,.0f}")
        m4.metric("Avg. Time", f"{df_traffic.iloc[:, 4].mean():.1f}s")

        # Visual Row 1: Traffic & Pages
        c1, c2 = st.columns(2)
        with c1:
            fig_traffic = px.pie(df_traffic, values=df_traffic.columns[1], names=df_traffic.columns[0], 
                                 title="Traffic Sources", hole=0.4)
            st.plotly_chart(fig_traffic, use_container_width=True)
        
        with c2:
            df_pages = pd.read_csv(data_path / "pages.csv", skiprows=9) if (data_path / "pages.csv").exists() else None
            if df_pages is not None:
                fig_pages = px.bar(df_pages.head(10), x=df_pages.columns[1], y=df_pages.columns[0], 
                                   orientation='h', title="Top Content", color_discrete_sequence=['#3498db'])
                st.plotly_chart(fig_pages, use_container_width=True)

        # Visual Row 2: Events
        st.subheader("Conversion & Event volume")
        df_events = pd.read_csv(data_path / "events.csv", skiprows=9) if (data_path / "events.csv").exists() else None
        if df_events is not None:
            fig_events = px.area(df_events.head(10), x=df_events.columns[0], y=df_events.columns[1], 
                                 title="Event Distribution", color_discrete_sequence=['#2ecc71'])
            st.plotly_chart(fig_events, use_container_width=True)
    else:
        st.warning("Awaiting local CSV data in /data/ folder.")

# --- TAB 2: GTM EXPLORER (Local JSON vs Uploaded JSON) ---
with tabs[1]:
    st.subheader("GTM Workspace Inspector")
    
    # Priority: 1. Uploaded JSON, 2. /data/container.json
    gtm_data = None
    if uploaded_json:
        gtm_data = json.load(uploaded_json)
        st.info("Using manually uploaded JSON file.")
    elif (data_path / "container.json").exists():
        with open(data_path / "container.json", "r") as f:
            gtm_data = json.load(f)
        st.success("Loaded default container from /data/container.json")

    if gtm_data:
        explorer = GTMExplorer(gtm_data)
        tag_names = [t['name'] for t in explorer.tags]
        
        col_search, col_audit = st.columns([2, 1])
        with col_search:
            selected_tag = st.selectbox("Search & Inspect Tag", ["Select a tag..."] + tag_names)
        
        if selected_tag != "Select a tag...":
            details = explorer.get_tag_details(selected_tag)
            with st.container(border=True):
                ca, cb, cc = st.columns(3)
                ca.write(f"**Type:** {details['Type']}")
                cb.write(f"**GA4 ID:** `{details['Measurement ID']}`")
                cc.write(f"**Status:** {'🟢 Active' if details['Live'] else '⚪ Paused'}")
                st.write(f"**Trigger:** `{details['Event Name']}`")
                
                # Placeholder for API Editing
                if st.session_state.get("api_active"):
                    if st.button(f"✏️ Edit {selected_tag}"):
                        st.text_input("New Event Name", value=details['Event Name'])
                        st.button("Push Change to GTM")

        st.divider()
        st.dataframe(pd.DataFrame([{"Tag": t['name'], "Type": t['type']} for t in explorer.tags]), use_container_width=True)
    else:
        st.info("Upload a GTM JSON or place container.json in /data to inspect tags.")

# --- TAB 3: SYSTEM STATUS ---
with tabs[2]:
    st.write(f"**Organization:** Leadar.digital")
    st.write(f"**Target Site:** Privacy Trust (Beite.co)")
    st.write(f"**GTM API Access:** {'Unlocked' if st.session_state.get('api_active') else 'Locked (Read-Only)'}")
