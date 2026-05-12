import streamlit as st
import pandas as pd
import json
import uuid
import plotly.express as px

# --- CORE LOGIC ---

class GTMManager:
    """Business logic for GTM auditing and tag generation."""
    def __init__(self, data=None):
        self.data = data or {}
        self.workspace = self.data.get("containerVersion", {})
        self.tags = self.workspace.get("tag", [])

    def check_conflict(self, name):
        return any(t['name'].lower() == name.lower() for t in self.tags)

    def generate_partial_json(self, config):
        """Creates a surgical JSON for GTM 'Merge' import."""
        return {
            "exportFormatVersion": 2,
            "containerVersion": {
                "tag": [{
                    "name": config['name'],
                    "type": "gaawe",
                    "parameter": [
                        {"type": "TEMPLATE", "key": "eventName", "value": config['event_name']},
                        {"type": "TEMPLATE", "key": "measurementId", "value": config['ga4_id']}
                    ],
                    "fingerprint": str(uuid.uuid4())
                }]
            }
        }

def load_clean_csv(uploaded_file):
    """Processes GA4 exports by skipping metadata rows."""
    if uploaded_file:
        return pd.read_csv(uploaded_file, skiprows=9)
    return None

# --- UI SETUP ---
st.set_page_config(page_title="Leadar Ops Console", layout="wide")

# Initialize Session State for the Wizard
if "step" not in st.session_state:
    st.session_state.step = 1
    st.session_state.new_tag = {}

# 1. SIDEBAR: DATA INPUTS
with st.sidebar:
    st.header("🔌 Data Connections")
    mode = st.radio("Primary Source", ["Manual File Upload", "Live API Sync"])
    
    if mode == "Live API Sync":
        with st.expander("GA4/GTM Credentials", expanded=True):
            st.text_input("Client ID", type="password")
            st.text_input("Client Secret", type="password")
            st.button("Connect & Refresh")
    else:
        st.subheader("📊 GA4 Exports")
        up_traffic = st.file_uploader("Traffic CSV", type="csv")
        up_events = st.file_uploader("Events CSV", type="csv")
        up_pages = st.file_uploader("Pages CSV", type="csv")
        
        st.divider()
        st.subheader("🏷️ GTM Workspace")
        up_gtm = st.file_uploader("Container JSON", type="json")

# 2. DATA RESOLUTION
df_traffic = load_clean_csv(up_traffic)
df_events = load_clean_csv(up_events)
df_pages = load_clean_csv(up_pages)
gtm_data = json.load(up_gtm) if up_gtm else None
manager = GTMManager(gtm_data)

# 3. MAIN INTERFACE
st.title("🚀 Marketing Operations Console")
tab1, tab2, tab3 = st.tabs(["📈 Lead Analytics", "🏷️ GTM Explorer", "🧙‍♂️ Tag Wizard"])

# --- TAB 1: ANALYTICS ---
with tab1:
    if df_traffic is not None:
        # Dynamic Filter Bar in the Body
        with st.container(border=True):
            channels = df_traffic.iloc[:, 0].unique().tolist()
            selected = st.multiselect("Active Channels", channels, default=channels)
        
        filtered = df_traffic[df_traffic.iloc[:, 0].isin(selected)]
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Sessions", f"{filtered.iloc[:, 1].sum():,.0f}")
        m2.metric("Key Events", f"{df_events.iloc[:, 1].sum() if df_events is not None else 0:,.0f}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(filtered, values=filtered.columns[1], names=filtered.columns[0], title="Traffic Source"), use_container_width=True)
        with c2:
            if df_pages is not None:
                st.plotly_chart(px.bar(df_pages.head(10), x=df_pages.columns[1], y=df_pages.columns[0], orientation='h', title="Top Pages"), use_container_width=True)
    else:
        st.info("👋 Welcome. Please upload your GA4 CSV exports in the sidebar to begin analysis.")

# --- TAB 2: EXPLORER ---
with tab2:
    if gtm_data:
        st.subheader("Current Workspace Inventory")
        tag_names = [t['name'] for t in manager.tags]
        selected_tag = st.selectbox("Select Tag to Inspect", ["Search..."] + tag_names)
        if selected_tag != "Search...":
            st.json(next(t for t in manager.tags if t['name'] == selected_tag))
    else:
        st.warning("Upload a GTM JSON in the sidebar to browse your tags.")

# --- TAB 3: WIZARD ---
with tab3:
    st.subheader("Tag Creation Wizard")
    # ... (Wizard steps 1-3 as previously built)
    if st.session_state.step == 1:
        name = st.text_input("Tag Name")
        if st.button("Check Conflicts & Next"):
            if manager.check_conflict(name):
                st.error("Name already exists!")
            else:
                st.session_state.new_tag['name'] = name
                st.session_state.step = 2
                st.rerun()
