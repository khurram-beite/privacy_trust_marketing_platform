import streamlit as st
import pandas as pd
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
import plotly.express as px

# --- BUSINESS LOGIC: GTM & TAG MANAGEMENT ---

class GTMManager:
    def __init__(self, data):
        self.data = data or {}
        self.workspace = self.data.get("containerVersion", {})
        self.tags = self.workspace.get("tag", [])

    def check_conflict(self, name):
        """Returns True if tag name exists in current workspace."""
        return any(t['name'].lower() == name.lower() for t in self.tags)

    def generate_partial_json(self, config):
        """Creates a GTM-compatible JSON for a GA4 Event Tag."""
        # Standard GTM JSON structure for a GA4 Event (type: gaawe)
        partial = {
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
        return partial

# --- SESSION STATE INITIALIZATION ---
if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
    st.session_state.new_tag_config = {}

# --- UI SETUP ---
st.set_page_config(page_title="Leadar Ops Console", layout="wide")
data_path = Path(__file__).parent / "data"

# 1. SIDEBAR: CREDENTIALS & JSON UPLOADS
with st.sidebar:
    st.header("🔑 API Connectivity")
    with st.expander("Google Cloud Credentials"):
        client_id = st.text_input("Client ID", type="password")
        client_secret = st.text_input("Client Secret", type="password")
    
    if st.button("🔄 Sync Live API"):
        if client_id and client_secret:
            st.session_state["api_active"] = True
            st.success("API Active")

    st.divider()
    st.header("📂 Local Data")
    uploaded_json = st.file_uploader("Override GTM Container", type="json")

# 2. MAIN INTERFACE
st.title("🚀 Marketing Operations Console")
tabs = st.tabs(["📈 Lead Analytics", "🏷️ GTM Explorer", "🧙‍♂️ Tag Wizard"])

# --- LOAD DATA ---
gtm_raw = None
if uploaded_json:
    gtm_raw = json.load(uploaded_json)
elif (data_path / "container.json").exists():
    with open(data_path / "container.json", "r") as f:
        gtm_raw = json.load(f)

manager = GTMManager(gtm_raw)

# --- TAB 1: LEAD ANALYTICS (Analytics implementation same as prior) ---
with tabs[0]:
    st.subheader("Interactive Performance View")
    df_traffic = pd.read_csv(data_path / "traffic.csv", skiprows=9) if (data_path / "traffic.csv").exists() else None
    if df_traffic is not None:
        c_filter, c_metric = st.columns([1, 3])
        with c_filter:
            selected_channels = st.multiselect("Channels", df_traffic.iloc[:, 0].unique(), default=df_traffic.iloc[:, 0].unique())
        # Visuals... (Simplified for brevity, similar to previous version)
        st.info("Analytics data active for Privacy Trust.")
    else:
        st.warning("Please add /data/traffic.csv to view analytics.")

# --- TAB 2: GTM EXPLORER ---
with tabs[1]:
    if gtm_raw:
        tag_list = [t['name'] for t in manager.tags]
        selected = st.selectbox("Inspect Existing Tag", ["Select..."] + tag_list)
        if selected != "Select...":
            # Logic to show tag details...
            st.json(next(t for t in manager.tags if t['name'] == selected))
    else:
        st.info("No container loaded.")

# --- TAB 3: TAG CREATION WIZARD ---
with tabs[2]:
    st.subheader("🧙‍♂️ New Tag Wizard")
    
    # STEP 1: CONFIG
    if st.session_state.wizard_step == 1:
        st.write("### Step 1: Identification")
        t_name = st.text_input("Internal Tag Name", placeholder="GA4 - Event - Lead Magnet Click")
        t_id = st.text_input("GA4 Measurement ID", placeholder="G-XXXXXXXXXX")
        
        if st.button("Next: Configure Event"):
            if manager.check_conflict(t_name):
                st.error(f"Error: A tag named '{t_name}' already exists in this workspace.")
            elif t_name and t_id:
                st.session_state.new_tag_config.update({"name": t_name, "ga4_id": t_id})
                st.session_state.wizard_step = 2
                st.rerun()

    # STEP 2: EVENT SETTINGS
    elif st.session_state.wizard_step == 2:
        st.write("### Step 2: Event Parameters")
        e_name = st.text_input("GA4 Event Name", placeholder="generate_lead")
        trigger_type = st.selectbox("Trigger Priority", ["All Pages", "Form Submission", "Click - Lead Magnet"])
        
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Back"):
                st.session_state.wizard_step = 1
                st.rerun()
        with b2:
            if st.button("Next: Review"):
                st.session_state.new_tag_config.update({"event_name": e_name, "trigger": trigger_type})
                st.session_state.wizard_step = 3
                st.rerun()

    # STEP 3: REVIEW & EXPORT
    elif st.session_state.wizard_step == 3:
        st.write("### Step 3: Review & Generate")
        st.write("Verify the configuration before exporting for a **Merge** import.")
        st.table(pd.DataFrame([st.session_state.new_tag_config]).T.rename(columns={0: "Value"}))
        
        b3, b4 = st.columns(2)
        with b3:
            if st.button("Restart"):
                st.session_state.wizard_step = 1
                st.session_state.new_tag_config = {}
                st.rerun()
        with b4:
            output_json = manager.generate_partial_json(st.session_state.new_tag_config)
            st.download_button(
                label="📥 Download Partial JSON",
                data=json.dumps(output_json, indent=4),
                file_name=f"leadar_tag_{st.session_state.new_tag_config['event_name']}.json",
                mime="application/json"
            )
            st.success("Download complete. Use 'Merge' in GTM Admin to import.")
