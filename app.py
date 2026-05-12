import streamlit as st
import pandas as pd
import json
import uuid
import plotly.express as px

# --- CORE BUSINESS LOGIC ---
import streamlit as st
import pandas as pd
import json
import uuid
import plotly.express as px
from datetime import datetime, timedelta

# --- CORE LOGIC ---

class WorkspaceManager:
    """Generic logic for GTM container auditing and snippet generation."""
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
    """Skips standard GA4 export metadata rows."""
    if file:
        return pd.read_csv(file, skiprows=9)
    return None

# --- UI SETUP ---
st.set_page_config(page_title="Marketing Operations Console", layout="wide")

if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
    st.session_state.tag_data = {}

# 1. SIDEBAR: CREDENTIALS & FILE UPLOADS
with st.sidebar:
    st.header("🔑 Connectivity")
    
    # Credentials Section (Anonymized)
    with st.expander("API Settings", expanded=False):
        st.text_input("Client ID", type="password", help="OAuth 2.0 Client ID")
        st.text_input("Client Secret", type="password", help="OAuth 2.0 Client Secret")
        st.text_input("GTM Workspace ID", placeholder="12345678")
        if st.button("Sync Live Data"):
            st.session_state["api_connected"] = True
            st.success("API Mode Active")

    st.divider()
    st.subheader("📁 Manual Data Imports")
    up_traffic = st.file_uploader("Traffic CSV", type="csv")
    up_pages = st.file_uploader("Pages CSV", type="csv")
    up_events = st.file_uploader("Events CSV", type="csv")
    up_gtm = st.file_uploader("GTM JSON", type="json")
    
    st.divider()
    org_label = st.text_input("Console Branding", value="Marketing Ops")

# 2. DATA LOADING
df_traffic = parse_ga4_csv(up_traffic)
df_pages = parse_ga4_csv(up_pages)
df_events = parse_ga4_csv(up_events)
gtm_json = json.load(up_gtm) if up_gtm else None
manager = WorkspaceManager(gtm_json)

# 3. MAIN INTERFACE
st.title(f"🚀 {org_label} Console")

t1, t2, t3 = st.tabs(["📊 Analytics", "🔍 GTM Inspector", "🧙‍♂️ Tag Wizard"])

# --- TAB 1: ANALYTICS ---
with t1:
    if df_traffic is not None:
        # TOP FILTER BAR
        with st.container(border=True):
            f1, f2 = st.columns([1, 2])
            with f1:
                # Date Picker (Visual only for CSV snapshots)
                st.date_input("Analysis Period", [datetime.now() - timedelta(days=30), datetime.now()])
            with f2:
                channels = df_traffic.iloc[:, 0].unique().tolist()
                selected_chan = st.multiselect("Filter Channels", channels, default=channels)
        
        filtered_df = df_traffic[df_traffic.iloc[:, 0].isin(selected_chan)]

        # Metrics & Graphs
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sessions", f"{filtered_df.iloc[:, 1].sum():,.0f}")
        m2.metric("Engagement %", f"{filtered_df.iloc[:, 3].mean():.2%}")
        m3.metric("Key Events", f"{df_events.iloc[:, 1].sum() if df_events is not None else 0:,.0f}")
        m4.metric("Avg. Time", f"{filtered_df.iloc[:, 4].mean():.1f}s")

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(filtered_df, values=filtered_df.columns[1], names=filtered_df.columns[0], title="Acquisition Share"), use_container_width=True)
            if df_events is not None:
                st.plotly_chart(px.bar(df_events.head(10), x=df_events.columns[0], y=df_events.columns[1], title="Event Distribution"), use_container_width=True)
        
        with c2:
            if df_pages is not None:
                st.plotly_chart(px.bar(df_pages.head(10), x=df_pages.columns[1], y=df_pages.columns[0], orientation='h', title="Top Content"), use_container_width=True)
                st.plotly_chart(px.scatter(df_pages.head(15), x=df_pages.columns[1], y=df_pages.columns[4], size=df_pages.columns[1], hover_name=df_pages.columns[0], title="Views vs. Engagement"), use_container_width=True)
    else:
        st.info("Upload GA4 CSV exports in the sidebar to view performance graphs.")

# --- TAB 2: GTM INSPECTOR ---
with t2:
    if gtm_json:
        tag_names = [t['name'] for t in manager.tags]
        target = st.selectbox("Select Tag", ["Search..."] + tag_names)
        if target != "Search...":
            st.json(next(t for t in manager.tags if t['name'] == target))
    else:
        st.warning("Upload a GTM JSON to browse tags.")

# --- TAB 3: TAG WIZARD ---
with t3:
    st.subheader("Step-by-Step Tag Creation")
    if st.session_state.wizard_step == 1:
        n = st.text_input("New Tag Name")
        tid = st.text_input("Measurement ID")
        if st.button("Next"):
            if manager.check_exists(n): st.error("Tag exists!")
            elif n and tid:
                st.session_state.tag_data.update({"name": n, "target_id": tid})
                st.session_state.wizard_step = 2
                st.rerun()

    elif st.session_state.wizard_step == 2:
        ev = st.text_input("GA4 Event Name")
        if st.button("Review"):
            st.session_state.tag_data['event_name'] = ev
            st.session_state.wizard_step = 3
            st.rerun()

    elif st.session_state.wizard_step == 3:
        st.write("### Configuration Summary")
        st.table(pd.DataFrame([st.session_state.tag_data]).T)
        out = manager.generate_tag_json(st.session_state.tag_data)
        st.download_button("Export JSON for Merge", data=json.dumps(out, indent=4), file_name="gtm_partial.json")
        if st.button("Reset"):
            st.session_state.wizard_step = 1
            st.rerun()
class WorkspaceInspector:
    """A white-label auditor for GTM containers."""
    def __init__(self, data=None):
        self.data = data or {}
        self.workspace = self.data.get("containerVersion", {})
        self.tags = self.workspace.get("tag", [])

    def check_name_exists(self, name):
        return any(t['name'].lower() == name.lower() for t in self.tags)

    def build_tag_json(self, config):
        """Generates a generic GA4 Event Tag JSON."""
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

def process_ga4_data(file):
    """Universal GA4 CSV parser."""
    if file:
        return pd.read_csv(file, skiprows=9)
    return None

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Marketing Ops Console", layout="wide")

if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = 1
    st.session_state.temp_tag = {}

# 1. SIDEBAR: ANONYMIZED CONFIG
with st.sidebar:
    st.header("⚙️ Configuration")
    org_name = st.text_input("Organization Name", value="Global Ops")
    property_label = st.text_input("Property Label", value="Main Website")
    
    st.divider()
    st.subheader("📁 Data Uploads")
    up_traffic = st.file_uploader("Traffic Acquisition CSV", type="csv")
    up_pages = st.file_uploader("Pages & Screens CSV", type="csv")
    up_events = st.file_uploader("Events CSV", type="csv")
    up_gtm = st.file_uploader("GTM Container JSON", type="json")

# 2. DATA RESOLUTION
df_traffic = process_ga4_data(up_traffic)
df_pages = process_ga4_data(up_pages)
df_events = process_ga4_data(up_events)
gtm_json = json.load(up_gtm) if up_gtm else None
inspector = WorkspaceInspector(gtm_json)

# 3. MAIN DASHBOARD
st.title(f"🚀 {org_name} | Operations Console")
st.caption(f"Currently Analyzing: {property_label}")

tab_ana, tab_gtm, tab_wiz = st.tabs(["📊 Performance Analytics", "🔍 GTM Inspector", "🧙‍♂️ Tag Wizard"])

# --- TAB: ANALYTICS (All Graphs Restored) ---
with tab_ana:
    if df_traffic is not None:
        # Filter Bar
        with st.container(border=True):
            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                st.write("**Data Filters**")
            with col_f2:
                chan_list = df_traffic.iloc[:, 0].unique().tolist()
                selected_chan = st.multiselect("Channels", chan_list, default=chan_list)
        
        mask = df_traffic.iloc[:, 0].isin(selected_chan)
        f_traffic = df_traffic[mask]

        # Top Metric Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Sessions", f"{f_traffic.iloc[:, 1].sum():,.0f}")
        m2.metric("Engagement Rate", f"{f_traffic.iloc[:, 3].mean():.2%}")
        m3.metric("Conversions", f"{df_events.iloc[:, 1].sum() if df_events is not None else 0:,.0f}")
        m4.metric("Avg. Engagement", f"{f_traffic.iloc[:, 4].mean():.1f}s")

        # Visual Grid
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(px.pie(f_traffic, values=f_traffic.columns[1], names=f_traffic.columns[0], 
                                 title="Traffic Share by Channel", hole=0.4), use_container_width=True)
            
            if df_events is not None:
                st.plotly_chart(px.bar(df_events.head(10), x=df_events.columns[0], y=df_events.columns[1], 
                                     title="Top Event Activity", color_discrete_sequence=['#ff7f0e']), use_container_width=True)
        
        with g2:
            if df_pages is not None:
                st.plotly_chart(px.bar(df_pages.head(12), x=df_pages.columns[1], y=df_pages.columns[0], 
                                     orientation='h', title="Top Content Performance"), use_container_width=True)
                
                # Additional Scatter for Engagement vs Views
                st.plotly_chart(px.scatter(df_pages.head(20), x=df_pages.columns[1], y=df_pages.columns[4], 
                                         size=df_pages.columns[1], hover_name=df_pages.columns[0],
                                         title="Engagement Depth vs. Popularity"), use_container_width=True)
    else:
        st.info("Please upload your CSV exports in the sidebar to populate the analytics suite.")

# --- TAB: GTM INSPECTOR ---
with tab_gtm:
    if gtm_json:
        tag_names = [t['name'] for t in inspector.tags]
        look_up = st.selectbox("Select Tag to Audit", ["Search..."] + tag_names)
        if look_up != "Search...":
            st.write(f"### Audit: {look_up}")
            st.json(next(t for t in inspector.tags if t['name'] == look_up))
    else:
        st.warning("Upload a GTM JSON to use the Inspector.")

# --- TAB: WIZARD ---
with tab_wiz:
    st.subheader("Tag Creation Wizard")
    if st.session_state.wizard_step == 1:
        st.write("Step 1: Identity")
        name = st.text_input("New Tag Name")
        target_id = st.text_input("Measurement ID (G-XXXX)")
        if st.button("Next"):
            if inspector.check_name_exists(name): st.error("Name conflict!")
            elif name and target_id:
                st.session_state.temp_tag.update({"name": name, "target_id": target_id})
                st.session_state.wizard_step = 2
                st.rerun()

    elif st.session_state.wizard_step == 2:
        st.write("Step 2: Logic")
        event = st.text_input("GA4 Event Name")
        if st.button("Generate Snippet"):
            st.session_state.temp_tag['event_name'] = event
            st.session_state.wizard_step = 3
            st.rerun()

    elif st.session_state.wizard_step == 3:
        st.write("Step 3: Export")
        st.table(pd.DataFrame([st.session_state.temp_tag]).T)
        final_json = inspector.build_tag_json(st.session_state.temp_tag)
        st.download_button("Download Merge JSON", data=json.dumps(final_json, indent=4), file_name="new_gtm_tag.json")
        if st.button("Start Over"):
            st.session_state.wizard_step = 1
            st.rerun()
