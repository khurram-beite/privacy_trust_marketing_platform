import streamlit as st
import pandas as pd
import json
import plotly.express as px
from pathlib import Path

# --- BUSINESS LOGIC: GTM INTELLIGENCE ---

class GTMExplorer:
    """Handles GTM data exploration and tag visualization."""
    def __init__(self, data):
        self.data = data.get("containerVersion", {})
        self.tags = self.data.get("tag", [])
        self.variables = self.data.get("variable", [])
    
    def get_tag_details(self, tag_name):
        """Extracts key parameters for a specific tag to make them human-readable."""
        tag = next((t for t in self.tags if t['name'] == tag_name), None)
        if not tag: return None
        
        # Simplifies complex GTM JSON into a clean dictionary
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

# 1. SIDEBAR FILTERS (Global Interactivity)
with st.sidebar:
    st.header("🎯 Filter Console")
    # Date Range (Mocking logic for CSV data)
    date_range = st.date_input("Analysis Period", [])
    
    # Load Data to populate filters
    data_path = Path(__file__).parent / "data"
    df_traffic = pd.read_csv(data_path / "traffic.csv", skiprows=9) if (data_path / "traffic.csv").exists() else None
    
    selected_channels = []
    if df_traffic is not None:
        channels = df_traffic.iloc[:, 0].unique().tolist()
        selected_channels = st.multiselect("Traffic Channels", channels, default=channels)

# 2. MAIN CONSOLE
st.title("🚀 Leadar Marketing Operations")
tabs = st.tabs(["📈 Lead Analytics", "🏷️ GTM Explorer", "📡 API Management"])

# --- TAB: LEAD ANALYTICS ---
with tabs[0]:
    if df_traffic is not None:
        # Apply Sidebar Filters
        mask = df_traffic.iloc[:, 0].isin(selected_channels)
        filtered_df = df_traffic[mask]

        # Top Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Sessions", f"{filtered_df.iloc[:, 1].sum():,.0f}")
        m2.metric("Avg. Engagement", f"{filtered_df.iloc[:, 3].mean():.2%}")
        m3.metric("Key Events", f"{filtered_df.iloc[:, 7].sum():,.0f}")

        # Visualizations
        c1, c2 = st.columns(2)
        with c1:
            fig_traffic = px.pie(filtered_df, values=filtered_df.columns[1], names=filtered_df.columns[0], 
                                 title="Traffic Composition", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_traffic, use_container_width=True)
        
        with c2:
            # Load Pages Data for performance chart
            df_pages = pd.read_csv(data_path / "pages.csv", skiprows=9) if (data_path / "pages.csv").exists() else None
            if df_pages is not None:
                fig_pages = px.bar(df_pages.head(10), x=df_pages.columns[1], y=df_pages.columns[0], 
                                   orientation='h', title="Top Performing Pages", color=df_pages.columns[1])
                st.plotly_chart(fig_pages, use_container_width=True)

        st.subheader("Event Distribution")
        df_events = pd.read_csv(data_path / "events.csv", skiprows=9) if (data_path / "events.csv").exists() else None
        if df_events is not None:
            fig_events = px.area(df_events.head(10), x=df_events.columns[0], y=df_events.columns[1], 
                                 title="Event Volume by Type")
            st.plotly_chart(fig_events, use_container_width=True)
    else:
        st.warning("Please add CSVs to /data/ folder to see analytics.")

# --- TAB: GTM EXPLORER ---
with tabs[1]:
    st.subheader("GTM Visual Inspector")
    local_gtm = data_path / "container.json"
    
    if local_gtm.exists():
        with open(local_gtm, "r") as f:
            explorer = GTMExplorer(json.load(f))
        
        # Interactive Search/Selection
        tag_names = [t['name'] for t in explorer.tags]
        selected_tag = st.selectbox("Select a Tag to Inspect", ["Select..."] + tag_names)
        
        if selected_tag != "Select...":
            details = explorer.get_tag_details(selected_tag)
            
            # Simplified Display Card
            with st.container(border=True):
                col_a, col_b, col_c = st.columns(3)
                col_a.write(f"**Type:** {details['Type']}")
                col_b.write(f"**GA4 ID:** {details['Measurement ID']}")
                col_c.write(f"**Status:** {'🟢 Active' if details['Live'] else '⚪ Paused'}")
                
                st.write(f"**Triggering Event:** `{details['Event Name']}`")
        
        st.divider()
        st.write("📊 **Full Tag Inventory**")
        st.dataframe(pd.DataFrame([{"Name": t['name'], "Type": t['type']} for t in explorer.tags]), use_container_width=True)
    else:
        st.info("Place your GTM export in /data/container.json to browse tags.")

# --- TAB: API MANAGEMENT ---
with tabs[2]:
    st.subheader("API Connectivity & Editing")
    st.info("Enter credentials to enable Live Sync and Tag Writing.")
    # (API input fields and refresh button as before)
