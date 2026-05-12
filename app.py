import streamlit as st
import pandas as pd
import json
import uuid
import plotly.express as px
from datetime import datetime, timedelta

# --- 1. GLOBAL CONFIG & STYLING ---
# Defining this at the top prevents the TypeError you saw earlier
PLOTLY_BASE = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Inter, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10)
)

class WorkspaceManager:
    """Logic for GTM container auditing and snippet generation."""
    def __init__(self, data=None):
        self.data = data or {}
        self.workspace = self.data.get("containerVersion", {})
        self.tags = self.workspace.get("tag", [])

    def check_exists(self, name):
        return any(t['name'].lower() == name.lower() for t in self.tags)

    def generate_tag_json(self, config):
        """Creates a GTM-compatible JSON for a GA4 Event."""
        return {
            "exportFormatVersion": 2,
            "containerVersion": {
                "tag": [{
                    "name": config['name'],
                    "type": "gaawe",
                    "parameter": [
                        {"type": "TEMPLATE", "key": "eventName", "value": config['event_name']},
                        {"type": "TEMPLATE", "key": "measurementId", "value": config['target_id']}
                    ],
                    "fingerprint": str(uuid.uuid4())
                }]
            }
        }

def parse_ga4_csv(file):
    if file:
        try:
            return pd.read_csv(file, skiprows=9)
        except Exception as e:
            st.error(f"Error parsing CSV: {e}")
    return None

# --- 2. UI SETUP ---
st.set_page_config(page_title="Marketing Operations Console", layout="wide")

if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
    st.session_state.tag_data = {}

# --- 3. SIDEBAR: CREDENTIALS & IMPORTS ---
with st.sidebar:
    st.header("🔑 API Connectivity")
    
    # Credentials Section
    with st.expander("API Configuration", expanded=True):
        client_id = st.text_input("Client ID", type="password")
        client_secret = st.text_input("Client Secret", type="password")
        workspace_id = st.text_input("GTM Workspace ID", placeholder="e.g., 123456789")
        
        if st.button("🔄 Sync Live Data"):
            if client_id and client_secret:
                st.session_state["api_connected"] = True
                st.success("API Sync Initiated...")
            else:
                st.warning("Credentials required for sync.")

    st.divider()
    st.subheader("📁 Manual Data Imports")
    up_traffic = st.file_uploader("Traffic Acquisition CSV", type="csv")
    up_pages = st.file_uploader("Pages & Screens CSV", type="csv")
    up_events = st.file_uploader("Events CSV", type="csv")
    up_gtm = st.file_uploader("GTM Container JSON", type="json")

# --- 4. DATA PROCESSING ---
df_traffic = parse_ga4_csv(up_traffic)
df_pages = parse_ga4_csv(up_pages)
df_events = parse_ga4_csv(up_events)
gtm_json = json.load(up_gtm) if up_gtm else None
manager = WorkspaceManager(gtm_json)

# --- 5. MAIN DASHBOARD ---
st.title("🚀 Marketing Operations Console")

tab_ana, tab_gtm, tab_wiz = st.tabs(["📊 Performance Analytics", "🔍 GTM Inspector", "🧙‍♂️ Tag Wizard"])

with tab_ana:
    if df_traffic is not None:
        # Filter Bar
        with st.container(border=True):
            f1, f2 = st.columns([1, 2])
            with f1:
                st.date_input("Analysis Period", [datetime.now() - timedelta(days=30), datetime.now()])
            with f2:
                channels = df_traffic.iloc[:, 0].unique().tolist()
                selected_chan = st.multiselect("Channels", channels, default=channels)
        
        filtered_df = df_traffic[df_traffic.iloc[:, 0].isin(selected_chan)]

        # KPI Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sessions", f"{filtered_df.iloc[:, 1].sum():,.0f}")
        m2.metric("Engagement %", f"{filtered_df.iloc[:, 3].mean():.1%}")
        m3.metric("Key Events", f"{df_events.iloc[:, 1].sum() if df_events is not None else 0:,.0f}")
        m4.metric("Avg. Time", f"{filtered_df.iloc[:, 4].mean():.1f}s")

        # Visualization Grid
        c1, c2 = st.columns(2)
        with c1:
            fig_acq = px.pie(filtered_df, values=filtered_df.columns[1], names=filtered_df.columns[0], 
                             title="Traffic Share", hole=0.4)
            fig_acq.update_layout(**PLOTLY_BASE)
            st.plotly_chart(fig_acq, use_container_width=True)

            if df_events is not None:
                fig_evt = px.bar(df_events.head(10), x=df_events.columns[0], y=df_events.columns[1], 
                                 title="Top Event Volume")
                fig_evt.update_layout(**PLOTLY_BASE)
                st.plotly_chart(fig_evt, use_container_width=True)
        
        with c2:
            if df_pages is not None:
                fig_pages = px.bar(df_pages.head(10), x=df_pages.columns[1], y=df_pages.columns[0], 
                                   orientation='h', title="Top Content Performance")
                fig_pages.update_layout(**PLOTLY_BASE)
                st.plotly_chart(fig_pages, use_container_width=True)

                fig_scatter = px.scatter(df_pages.head(15), x=df_pages.columns[1], y=df_pages.columns[4], 
                                         size=df_pages.columns[1], hover_name=df_pages.columns[0], 
                                         title="Engagement Depth vs. Views")
                fig_scatter.update_layout(**PLOTLY_BASE)
                st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Upload GA4 CSV exports in the sidebar to populate analytics.")

# --- 6. GTM INSPECTOR & WIZARD (RETAINED) ---
# [Tabs 2 and 3 remain same as your logic, ensuring they reference 'manager']
