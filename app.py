"""
Marketing Operations Console — Streamlit App
Beite.co / Privacy Trust
--------------------------------------------
Tabs:
  1. Analytics        — traffic, acquisition, engagement
  2. Opportunities    — lead magnets, form performance, conversion candidates
  3. GTM Inspector    — tag browser + tag wizard (local JSON + live API sync)

Run:  streamlit run marketing_ops_console.py
Deps: pip install streamlit pandas plotly requests
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json, uuid, re, time
from io import StringIO

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Marketing Ops Console",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CUSTOM CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Metric card tidy */
[data-testid="metric-container"] { background:#f8f9fa; border-radius:10px; padding:14px 18px; }
/* Tab font */
button[data-baseweb="tab"] { font-size:14px; font-weight:500; }
/* Sidebar section headers */
.sidebar-section { font-size:11px; text-transform:uppercase; letter-spacing:.06em;
                   color:#888; font-weight:600; margin:12px 0 4px; }
/* Tag badge */
.tag-badge { display:inline-block; font-size:10px; padding:2px 8px; border-radius:6px;
             font-weight:600; margin-right:4px; }
.badge-ga4   { background:#dbeafe; color:#1e40af; }
.badge-ads   { background:#fef3c7; color:#92400e; }
.badge-html  { background:#dcfce7; color:#166534; }
.badge-other { background:#f1f5f9; color:#475569; }
/* Opportunity card */
.opp-card { border-left:4px solid #3b82f6; background:#f0f7ff;
            padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:10px; }
.opp-card.high { border-left-color:#ef4444; background:#fff5f5; }
.opp-card.medium { border-left-color:#f59e0b; background:#fffbeb; }
</style>
""", unsafe_allow_html=True)

# ─── HELPERS ────────────────────────────────────────────────────────────────
def parse_ga4_csv(src) -> pd.DataFrame | None:
    """Skip GA4 export header rows (comment lines starting with #)."""
    if src is None:
        return None
    try:
        if hasattr(src, "read"):
            raw = src.read().decode("utf-8", errors="replace")
        else:
            with open(src, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        lines = [l for l in raw.splitlines() if not l.startswith("#")]
        return pd.read_csv(StringIO("\n".join(lines)))
    except Exception as e:
        st.sidebar.error(f"CSV parse error: {e}")
        return None


def clean_path(p: str) -> str:
    """Trim long page paths for display."""
    if len(p) > 55:
        return p[:52] + "…"
    return p


def fmt_num(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def tag_type_label(t: str) -> str:
    mapping = {"gaawe": "GA4", "googtag": "GA4", "awct": "ADS",
               "gclidw": "ADS", "html": "HTML"}
    return mapping.get(t.lower(), "OTHER")


def badge_html(label: str) -> str:
    cls = {"GA4": "badge-ga4", "ADS": "badge-ads",
           "HTML": "badge-html"}.get(label, "badge-other")
    return f'<span class="tag-badge {cls}">{label}</span>'

# ─── GTM API HELPERS ────────────────────────────────────────────────────────
GTM_BASE = "https://www.googleapis.com/tagmanager/v2"

def gtm_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str | None:
    """Exchange a refresh token for an access token."""
    if not HAS_REQUESTS:
        st.error("requests library not installed. Run: pip install requests")
        return None
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    if resp.ok:
        return resp.json().get("access_token")
    st.error(f"Token error: {resp.status_code} — {resp.text[:200]}")
    return None

def gtm_get_workspaces(account_id: str, container_id: str, token: str) -> list:
    if not HAS_REQUESTS:
        return []
    path = f"{GTM_BASE}/accounts/{account_id}/containers/{container_id}/workspaces"
    r = requests.get(path, headers=gtm_headers(token), timeout=10)
    if r.ok:
        return r.json().get("workspace", [])
    st.error(f"GTM API error: {r.status_code}")
    return []

def gtm_list_tags(account_id: str, container_id: str, workspace_id: str, token: str) -> list:
    if not HAS_REQUESTS:
        return []
    path = f"{GTM_BASE}/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/tags"
    r = requests.get(path, headers=gtm_headers(token), timeout=10)
    return r.json().get("tag", []) if r.ok else []

def gtm_create_tag(account_id: str, container_id: str, workspace_id: str,
                   token: str, tag_body: dict) -> dict | None:
    if not HAS_REQUESTS:
        return None
    path = f"{GTM_BASE}/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/tags"
    r = requests.post(path, headers=gtm_headers(token), json=tag_body, timeout=10)
    if r.ok:
        return r.json()
    st.error(f"Tag create error: {r.status_code} — {r.text[:300]}")
    return None

def gtm_list_triggers(account_id: str, container_id: str, workspace_id: str, token: str) -> list:
    if not HAS_REQUESTS:
        return []
    path = f"{GTM_BASE}/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/triggers"
    r = requests.get(path, headers=gtm_headers(token), timeout=10)
    return r.json().get("trigger", []) if r.ok else []

# ─── OPPORTUNITY ENGINE ─────────────────────────────────────────────────────
FORM_KEYWORDS  = ["contact", "demo", "request", "connect", "booking", "lead",
                  "assessment", "lp", "hib", "consultation"]
LEAD_KEYWORDS  = ["resources", "download", "checklist", "guide", "assessment",
                  "webinar", "ebook", "report", "whitepaper", "template"]
CONV_KEYWORDS  = ["contact", "demo", "request", "connect", "thank", "booking",
                  "quote", "pricing", "buy", "purchase", "checkout"]

def score_page(row: pd.Series, pages_df: pd.DataFrame) -> dict:
    path = str(row.iloc[0]).lower()
    views = row.iloc[1]
    eng_time = row.iloc[3]
    key_events = row.iloc[6] if len(row) > 6 else 0

    is_form = any(k in path for k in FORM_KEYWORDS)
    is_lead = any(k in path for k in LEAD_KEYWORDS)
    is_conv = any(k in path for k in CONV_KEYWORDS)

    # High engagement + decent views = lead magnet candidate
    avg_eng = pages_df.iloc[:, 3].mean()
    avg_views = pages_df.iloc[:, 1].mean()

    lead_score = 0
    if is_lead:       lead_score += 40
    if eng_time > avg_eng * 1.5: lead_score += 30
    if views > avg_views * 0.5:  lead_score += 20
    if key_events > 0:           lead_score += 10

    form_score = 0
    if is_form:       form_score += 50
    if key_events > 0: form_score += 30
    if eng_time > 15:  form_score += 20

    conv_score = 0
    if is_conv:       conv_score += 40
    if key_events > 0: conv_score += 40
    if views > avg_views: conv_score += 20

    return {
        "path": row.iloc[0],
        "views": views,
        "engaged_time": eng_time,
        "key_events": key_events,
        "lead_score": lead_score,
        "form_score": form_score,
        "conv_score": conv_score,
        "is_form": is_form,
        "is_lead": is_lead,
        "is_conv": is_conv,
    }

def identify_opportunities(pages_df: pd.DataFrame, events_df: pd.DataFrame | None) -> pd.DataFrame:
    scored = [score_page(row, pages_df) for _, row in pages_df.iterrows()]
    return pd.DataFrame(scored)

# ─── SESSION STATE ───────────────────────────────────────────────────────────
for key, default in {
    "gtm_token": None,
    "gtm_workspaces": [],
    "gtm_live_tags": [],
    "gtm_live_triggers": [],
    "wizard_step": 1,
    "wizard_data": {},
    "api_connected": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚀 Marketing Ops Console")
    st.caption("Beite.co / Privacy Trust")
    st.divider()

    # ── Local file uploads ────────────────────────────────────────────────
    st.markdown('<p class="sidebar-section">📁 Local Data Files</p>', unsafe_allow_html=True)

    up_traffic = st.file_uploader("Traffic CSV", type="csv", key="up_traffic")
    up_pages   = st.file_uploader("Pages CSV",   type="csv", key="up_pages")
    up_events  = st.file_uploader("Events CSV",  type="csv", key="up_events")
    up_gtm     = st.file_uploader("GTM JSON",    type="json", key="up_gtm")

    st.divider()

    # ── Live API credentials ──────────────────────────────────────────────
    st.markdown('<p class="sidebar-section">🔑 GTM Live Sync</p>', unsafe_allow_html=True)
    with st.expander("OAuth2 Credentials", expanded=False):
        cred_client_id     = st.text_input("Client ID",     type="password", key="cred_cid")
        cred_client_secret = st.text_input("Client Secret", type="password", key="cred_cs")
        cred_refresh_token = st.text_input("Refresh Token", type="password", key="cred_rt",
                                           help="Generate via Google OAuth Playground")
        cred_account_id    = st.text_input("GTM Account ID",   placeholder="6249944329", key="cred_acc")
        cred_container_id  = st.text_input("GTM Container ID", placeholder="195604748",  key="cred_con")

        if st.button("🔄 Connect to GTM API"):
            if not HAS_REQUESTS:
                st.error("pip install requests")
            elif not all([cred_client_id, cred_client_secret, cred_refresh_token]):
                st.warning("Enter Client ID, Secret and Refresh Token.")
            else:
                with st.spinner("Authenticating…"):
                    token = get_access_token(cred_client_id, cred_client_secret, cred_refresh_token)
                if token:
                    st.session_state.gtm_token = token
                    st.session_state.api_connected = True
                    ws = gtm_get_workspaces(cred_account_id, cred_container_id, token)
                    st.session_state.gtm_workspaces = ws
                    st.success(f"✅ Connected — {len(ws)} workspace(s) found")
                else:
                    st.error("Authentication failed.")

    if st.session_state.api_connected:
        st.success("🟢 API connected")
    else:
        st.info("🔵 Local mode")

    st.divider()
    org_label = st.text_input("Console label", value="Privacy Trust")

# ─── DATA LOADING ─────────────────────────────────────────────────────────────
df_traffic = parse_ga4_csv(up_traffic)
df_pages   = parse_ga4_csv(up_pages)
df_events  = parse_ga4_csv(up_events)

gtm_data = None
if up_gtm:
    try:
        gtm_data = json.load(up_gtm)
    except Exception as e:
        st.error(f"GTM JSON parse error: {e}")

# Build a WorkspaceManager from whichever source is available
class WorkspaceManager:
    def __init__(self, data=None):
        self.data = data or {}
        cv = self.data.get("containerVersion", self.data)
        self.tags      = cv.get("tag", [])
        self.triggers  = cv.get("trigger", [])
        self.variables = cv.get("variable", [])
        self.container = cv.get("container", {})

    def check_exists(self, name: str) -> bool:
        return any(t["name"].lower() == name.lower() for t in self.tags)

    def tag_trigger_name(self, trigger_ids: list) -> str:
        id_map = {t["triggerId"]: t["name"] for t in self.triggers}
        names = [id_map.get(tid, f"ID {tid}") for tid in trigger_ids]
        return ", ".join(names) if names else "—"

    def generate_tag_body(self, cfg: dict, for_api=False) -> dict:
        params = [
            {"type": "TEMPLATE", "key": "eventName",      "value": cfg["event_name"]},
            {"type": "TEMPLATE", "key": "measurementId",  "value": cfg["measurement_id"]},
        ]
        if cfg.get("form_id"):
            params.append({"type": "TEMPLATE", "key": "eventParameters",
                           "value": json.dumps([{"name": "form_id", "value": cfg["form_id"]}])})
        body = {
            "name": cfg["name"],
            "type": "gaawe",
            "parameter": params,
            "tagFiringOption": "ONCE_PER_EVENT",
        }
        if cfg.get("trigger_id"):
            body["firingTriggerId"] = [cfg["trigger_id"]]
        if not for_api:
            body["fingerprint"] = str(uuid.uuid4())
        return body

    def export_json(self, cfg: dict) -> dict:
        return {
            "exportFormatVersion": 2,
            "exportTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "containerVersion": {
                "path": self.data.get("containerVersion", {}).get("path", ""),
                "accountId": self.data.get("containerVersion", {}).get("accountId", ""),
                "containerId": self.data.get("containerVersion", {}).get("containerId", ""),
                "tag": [self.generate_tag_body(cfg)],
                "trigger": [],
                "variable": [],
            }
        }

manager = WorkspaceManager(gtm_data)

# If live tags were fetched, merge them in for display
live_tags = st.session_state.gtm_live_tags
display_tags = live_tags if live_tags else manager.tags

# ─── PLOTLY THEME HELPERS ────────────────────────────────────────────────────
CHAN_COLORS = ["#3b82f6","#10b981","#f59e0b","#8b5cf6","#ef4444","#ec4899","#6b7280"]
CHART_H     = dict(margin=dict(t=30, b=30, l=10, r=10), height=300,
                    font=dict(size=12), plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)")

def styled(fig, h=300):
    fig.update_layout(
        height=h,
        margin=dict(t=30, b=50, l=10, r=10),
        font=dict(size=11),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="rgba(0,0,0,.06)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(0,0,0,.06)", zeroline=False)
    return fig

# ─── MAIN TITLE ──────────────────────────────────────────────────────────────
st.title(f"🚀 {org_label} — Marketing Ops Console")
st.caption("GA4 Analytics · Conversion Opportunities · GTM Inspector & Tag Wizard")

TAB_ANALYTICS, TAB_OPPS, TAB_GTM = st.tabs([
    "📊 Analytics",
    "🎯 Opportunities",
    "🔧 GTM Inspector & Wizard",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
with TAB_ANALYTICS:
    if df_traffic is None and df_pages is None and df_events is None:
        st.info("⬆️ Upload your GA4 CSV exports in the sidebar to view analytics.")
        st.stop()

    # ── Channel filter ────────────────────────────────────────────────────
    if df_traffic is not None:
        chan_col = df_traffic.columns[0]
        all_channels = df_traffic[chan_col].unique().tolist()
        selected = st.multiselect("Filter channels", all_channels, default=all_channels,
                                  key="chan_filter")
        tdf = df_traffic[df_traffic[chan_col].isin(selected)]
    else:
        tdf = None

    # ── KPI metrics ───────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    if tdf is not None:
        k1.metric("Sessions",          fmt_num(tdf.iloc[:,1].sum()))
        k2.metric("Engaged Sessions",  fmt_num(tdf.iloc[:,2].sum()))
        k3.metric("Avg Engagement %",  f"{tdf.iloc[:,3].mean()*100:.1f}%")
        k4.metric("Avg Eng. Time",     f"{tdf.iloc[:,4].mean():.1f}s")
    if df_events is not None:
        conv_events = df_events[df_events.iloc[:,0].isin(
            ["generate_lead","form_submit","booking_form_submit"]
        )].iloc[:,1].sum()
        k5.metric("Conversion Events", fmt_num(conv_events))

    st.divider()

    # ── Row 1: Acquisition + Engagement Rate ─────────────────────────────
    c1, c2 = st.columns(2)
    if tdf is not None:
        with c1:
            st.subheader("Acquisition Share")
            fig = px.pie(tdf, values=tdf.columns[1], names=tdf.columns[0],
                         color_discrete_sequence=CHAN_COLORS, hole=0.45)
            fig.update_traces(textposition="outside", textinfo="label+percent",
                              hovertemplate="%{label}: %{value:,} sessions<extra></extra>")
            fig.update_layout(height=320, margin=dict(t=10,b=10,l=10,r=10),
                              showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.subheader("Engagement Rate by Channel")
            eng = tdf.copy()
            eng["eng_pct"] = eng.iloc[:,3] * 100
            eng = eng.sort_values("eng_pct", ascending=True)
            fig = px.bar(eng, x="eng_pct", y=eng.columns[0], orientation="h",
                         color=eng.columns[0], color_discrete_sequence=CHAN_COLORS,
                         labels={"eng_pct": "Engagement %", eng.columns[0]: "Channel"})
            fig.update_traces(hovertemplate="%{y}: %{x:.1f}%<extra></extra>")
            fig.update_layout(**CHART_H)
            fig.update_xaxes(title="Engagement %", ticksuffix="%")
            fig.update_yaxes(title="")
            st.plotly_chart(styled(fig, 320), use_container_width=True)

    # ── Row 2: Events ─────────────────────────────────────────────────────
    if df_events is not None:
        st.subheader("Event Distribution")

        # Colour by semantic category
        def evt_color(name):
            system = ["page_view","session_start","first_visit","GA Configuration","user_engagement"]
            conv   = ["generate_lead","form_submit","booking_form_submit","form_start"]
            if name in system: return "#94a3b8"
            if name in conv:   return "#ef4444"
            return "#3b82f6"

        edf = df_events.copy()
        edf["color"] = edf.iloc[:,0].apply(evt_color)
        edf["category"] = edf.iloc[:,0].apply(
            lambda n: "System/Config" if n in ["page_view","session_start","first_visit",
                                               "GA Configuration","user_engagement"]
            else ("Conversion" if n in ["generate_lead","form_submit","booking_form_submit","form_start"]
                  else "Behaviour")
        )
        edf_sorted = edf.sort_values(edf.columns[1], ascending=True)

        fig = px.bar(edf_sorted, x=edf_sorted.columns[1], y=edf_sorted.columns[0],
                     orientation="h", color="category",
                     color_discrete_map={
                         "System/Config": "#94a3b8",
                         "Behaviour":     "#3b82f6",
                         "Conversion":    "#ef4444",
                     },
                     labels={edf_sorted.columns[1]: "Event Count", edf_sorted.columns[0]: "Event"},
                     height=max(320, len(edf_sorted)*38))
        fig.update_traces(hovertemplate="%{y}: %{x:,}<extra></extra>")
        fig.update_layout(margin=dict(t=30,b=40,l=10,r=10),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          legend=dict(title="", orientation="h", y=1.02, x=0))
        fig.update_xaxes(gridcolor="rgba(0,0,0,.06)")
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Pages ──────────────────────────────────────────────────────
    if df_pages is not None:
        st.subheader("Top 20 Pages — Views")
        pdf = df_pages.head(20).copy()
        pdf["label"] = pdf.iloc[:,0].apply(clean_path)

        fig = px.bar(pdf, x=pdf.columns[1], y="label", orientation="h",
                     color=pdf.columns[1], color_continuous_scale="Blues",
                     labels={pdf.columns[1]: "Views", "label": "Page Path"})
        fig.update_coloraxes(showscale=False)
        fig.update_traces(hovertemplate="%{y}: %{x:,} views<extra></extra>")
        n = len(pdf)
        fig.update_layout(height=max(360, n*32), margin=dict(t=30,b=40,l=10,r=30),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(autorange="reversed"))
        fig.update_xaxes(gridcolor="rgba(0,0,0,.06)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Views vs Avg Engagement Time (Top 25)")
        scatter_df = df_pages.head(25).copy()
        scatter_df["label"] = scatter_df.iloc[:,0].apply(clean_path)
        scatter_df["key_events"] = scatter_df.iloc[:,6]
        fig = px.scatter(
            scatter_df, x=scatter_df.columns[1], y=scatter_df.columns[3],
            size=scatter_df.columns[1], hover_name="label",
            color="key_events", color_continuous_scale="RdYlGn",
            labels={
                scatter_df.columns[1]: "Views",
                scatter_df.columns[3]: "Avg Engagement Time (s)",
                "key_events": "Key Events",
            },
            size_max=40,
        )
        fig.update_traces(
            hovertemplate="<b>%{hovertext}</b><br>Views: %{x:,}<br>Eng. time: %{y:.1f}s<extra></extra>"
        )
        fig.update_layout(height=420, margin=dict(t=30,b=40,l=10,r=10),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig.update_xaxes(gridcolor="rgba(0,0,0,.06)")
        fig.update_yaxes(gridcolor="rgba(0,0,0,.06)")
        st.plotly_chart(fig, use_container_width=True)

    # ── Avg engagement time by channel ────────────────────────────────────
    if tdf is not None:
        st.subheader("Avg Engagement Time per Session")
        tdf_sorted = tdf.sort_values(tdf.columns[4], ascending=False)
        fig = px.bar(tdf_sorted, x=tdf_sorted.columns[0], y=tdf_sorted.columns[4],
                     color=tdf_sorted.columns[0], color_discrete_sequence=CHAN_COLORS,
                     labels={tdf_sorted.columns[4]: "Avg Time (s)", tdf_sorted.columns[0]: ""})
        fig.update_traces(hovertemplate="%{x}: %{y:.1f}s<extra></extra>")
        fig.update_layout(**CHART_H)
        fig.update_yaxes(ticksuffix="s")
        st.plotly_chart(styled(fig), use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — OPPORTUNITIES
# ════════════════════════════════════════════════════════════════════════════
with TAB_OPPS:
    if df_pages is None:
        st.info("⬆️ Upload Pages CSV to identify conversion opportunities.")
        st.stop()

    opps = identify_opportunities(df_pages, df_events)
    avg_views = opps["views"].mean()
    avg_eng   = opps["engaged_time"].mean()

    st.markdown("### 🔴 Conversion Candidates — Pages to Tag as Key Events")
    conv_df = opps[opps["conv_score"] >= 40].sort_values("conv_score", ascending=False).head(12)
    if conv_df.empty:
        st.info("No high-priority conversion pages detected.")
    else:
        for _, row in conv_df.iterrows():
            priority = "high" if row["conv_score"] >= 70 else "medium"
            reasons = []
            if row["key_events"] > 0:  reasons.append(f"🎯 {int(row['key_events'])} key events already firing")
            if row["views"] > avg_views: reasons.append(f"📈 {int(row['views']):,} views (above avg)")
            if row["engaged_time"] > avg_eng: reasons.append(f"⏱ {row['engaged_time']:.0f}s avg engagement")
            rec = "Create a GA4 Key Event tag for this page."
            if row["is_form"]: rec = "Tag the form submission on this page as `generate_lead` or `form_submit`."
            st.markdown(f"""
<div class="opp-card {priority}">
  <strong>{row['path']}</strong><br>
  <small>{'  ·  '.join(reasons) if reasons else 'Conversion intent page'}</small><br>
  <small>💡 <em>{rec}</em></small>
</div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🧲 Lead Magnet Candidates — High Engagement, Low Conversion")
    lead_df = opps[(opps["lead_score"] >= 30) & (opps["key_events"] == 0)]\
        .sort_values("lead_score", ascending=False).head(10)
    if lead_df.empty:
        st.info("No lead magnet candidates detected.")
    else:
        fig = px.bar(
            lead_df, x="lead_score", y=lead_df["path"].apply(clean_path),
            orientation="h", color="engaged_time", color_continuous_scale="Tealrose",
            labels={"lead_score": "Lead Magnet Score", "y": "Page", "engaged_time": "Eng. Time (s)"},
            hover_data={"views": True, "engaged_time": ":.1f"},
        )
        fig.update_layout(height=max(300, len(lead_df)*38),
                          margin=dict(t=30,b=40,l=10,r=20),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(autorange="reversed"))
        fig.update_xaxes(gridcolor="rgba(0,0,0,.06)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("High-engagement pages with no key events — strong candidates to add a content download or gated form.")

    st.divider()
    st.markdown("### 📝 Form Performance — Tagging Priority")

    # Identify form-like pages from pages df
    form_pages = opps[opps["is_form"]].sort_values("form_score", ascending=False)
    if form_pages.empty:
        st.info("No form pages detected from page paths.")
    else:
        # Check what's already tagged in GTM
        tagged_paths = set()
        for tag in display_tags:
            for param in tag.get("parameter", []):
                if "value" in param and "/" in str(param["value"]):
                    tagged_paths.add(str(param["value"]).lower())

        fp_display = form_pages.copy()
        fp_display["already_tagged"] = fp_display["path"].apply(
            lambda p: "✅" if any(t in p.lower() for t in tagged_paths) else "❌"
        )
        fp_display["views"] = fp_display["views"].astype(int)
        fp_display["key_events"] = fp_display["key_events"].astype(int)
        fp_display["engaged_time"] = fp_display["engaged_time"].round(1)
        fp_display["form_score"] = fp_display["form_score"].astype(int)

        st.dataframe(
            fp_display[["path","views","key_events","engaged_time","form_score","already_tagged"]]
                .rename(columns={
                    "path": "Page Path", "views": "Views",
                    "key_events": "Key Events", "engaged_time": "Eng. Time (s)",
                    "form_score": "Priority Score", "already_tagged": "GTM Tagged?"
                }),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.markdown("### 📊 Engagement vs Key Events — Bubble Map")
    top_df = df_pages.head(30).copy()
    top_df["label"] = top_df.iloc[:,0].apply(clean_path)
    top_df["key_events"] = top_df.iloc[:,6]
    top_df["views"] = top_df.iloc[:,1]
    top_df["eng_time"] = top_df.iloc[:,3]

    fig = px.scatter(
        top_df, x="views", y="eng_time",
        size="views", color="key_events",
        hover_name="label",
        color_continuous_scale="Reds",
        size_max=50,
        labels={"views": "Page Views", "eng_time": "Avg Eng. Time (s)", "key_events": "Key Events"},
    )
    fig.update_traces(
        hovertemplate="<b>%{hovertext}</b><br>Views: %{x:,}<br>Eng: %{y:.1f}s<extra></extra>"
    )
    fig.update_layout(height=440, margin=dict(t=30,b=40,l=10,r=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(gridcolor="rgba(0,0,0,.06)")
    fig.update_yaxes(gridcolor="rgba(0,0,0,.06)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Bubble size = page views · Color = key events already firing · Pages in the top-right quadrant with no red color are prime tagging targets.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — GTM INSPECTOR & WIZARD
# ════════════════════════════════════════════════════════════════════════════
with TAB_GTM:
    if not gtm_data and not display_tags:
        st.info("⬆️ Upload a GTM JSON export **or** connect via the API sidebar to inspect your container.")
        st.stop()

    # ── Live sync button ──────────────────────────────────────────────────
    if st.session_state.api_connected and st.session_state.gtm_workspaces:
        with st.expander("🔄 Sync Live Tags from GTM API", expanded=False):
            ws_options = {ws["name"]: ws["workspaceId"]
                          for ws in st.session_state.gtm_workspaces}
            ws_name = st.selectbox("Workspace", list(ws_options.keys()), key="ws_select")
            ws_id   = ws_options[ws_name]
            if st.button("Pull Tags from GTM"):
                with st.spinner("Fetching…"):
                    live = gtm_list_tags(
                        st.session_state.get("cred_acc",""),
                        st.session_state.get("cred_con",""),
                        ws_id,
                        st.session_state.gtm_token,
                    )
                    live_triggers = gtm_list_triggers(
                        st.session_state.get("cred_acc",""),
                        st.session_state.get("cred_con",""),
                        ws_id,
                        st.session_state.gtm_token,
                    )
                    st.session_state.gtm_live_tags = live
                    st.session_state.gtm_live_triggers = live_triggers
                    st.success(f"Pulled {len(live)} tags and {len(live_triggers)} triggers.")
                    st.rerun()

    # Resolve which tags/triggers to display
    tags_to_show     = st.session_state.gtm_live_tags or manager.tags
    triggers_to_show = st.session_state.gtm_live_triggers or manager.triggers

    SOURCE_LABEL = "🟢 Live API" if st.session_state.gtm_live_tags else "🔵 Local JSON"

    # ── Inspector ─────────────────────────────────────────────────────────
    st.subheader(f"Container Inspector  {SOURCE_LABEL}")

    ins_col, detail_col = st.columns([1, 1.4])

    with ins_col:
        # Summary counts
        m1, m2, m3 = st.columns(3)
        m1.metric("Tags",      len(tags_to_show))
        m2.metric("Triggers",  len(triggers_to_show))
        m3.metric("Variables", len(manager.variables))

        st.markdown("**Select a tag to inspect:**")

        # Build type distribution donut
        type_counts = {}
        for t in tags_to_show:
            lbl = tag_type_label(t.get("type",""))
            type_counts[lbl] = type_counts.get(lbl, 0) + 1

        if type_counts:
            fig = px.pie(
                names=list(type_counts.keys()),
                values=list(type_counts.values()),
                color_discrete_sequence=["#3b82f6","#f59e0b","#10b981","#6b7280"],
                hole=0.5,
            )
            fig.update_traces(textposition="outside", textinfo="label+value")
            fig.update_layout(height=200, margin=dict(t=10,b=10,l=10,r=10),
                               showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        tag_options = ["— Select a tag —"] + [t["name"] for t in tags_to_show]
        selected_tag_name = st.selectbox("Tag", tag_options, key="tag_select")

    with detail_col:
        if selected_tag_name and selected_tag_name != "— Select a tag —":
            tag_obj = next((t for t in tags_to_show if t["name"] == selected_tag_name), None)
            if tag_obj:
                ttype = tag_obj.get("type","")
                tlabel = tag_type_label(ttype)
                st.markdown(
                    f"**{tag_obj['name']}**  "
                    f"{badge_html(tlabel)} "
                    f"<small style='color:#666'>type: <code>{ttype}</code>  ·  ID {tag_obj.get('tagId','—')}</small>",
                    unsafe_allow_html=True,
                )
                # Trigger names
                firing_ids = tag_obj.get("firingTriggerId", [])
                trig_names = []
                trig_map = {t["triggerId"]: t["name"] for t in triggers_to_show}
                for fid in firing_ids:
                    trig_names.append(trig_map.get(fid, f"ID {fid}"))
                if trig_names:
                    st.markdown(f"⚡ **Trigger(s):** {', '.join(trig_names)}")

                st.markdown("**Parameters:**")
                params = tag_obj.get("parameter", [])
                if params:
                    param_df = pd.DataFrame([
                        {"Key": p.get("key",""), "Type": p.get("type",""), "Value": str(p.get("value",""))[:80]}
                        for p in params
                    ])
                    st.dataframe(param_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No parameters.")

                with st.expander("Raw JSON"):
                    st.json(tag_obj)
        else:
            st.info("Select a tag from the dropdown to inspect its configuration.")

    # ── Trigger list ──────────────────────────────────────────────────────
    if triggers_to_show:
        st.divider()
        st.subheader("Triggers")
        trig_df = pd.DataFrame([{
            "ID":      t.get("triggerId",""),
            "Name":    t.get("name",""),
            "Type":    t.get("type",""),
            "Details": ", ".join(
                f"{f.get('key','')}={f.get('value','')}"
                for f in t.get("filter",[])[:2]
            ) or "—"
        } for t in triggers_to_show])
        st.dataframe(trig_df, use_container_width=True, hide_index=True)

    # ── Variables ─────────────────────────────────────────────────────────
    if manager.variables:
        st.divider()
        st.subheader("Variables")
        var_df = pd.DataFrame([{
            "ID": v.get("variableId",""),
            "Name": v.get("name",""),
            "Type": v.get("type",""),
            "Value": next((p.get("value","") for p in v.get("parameter",[])
                           if p.get("key") in ("value","dataLayerVersion","name")), "—")
        } for v in manager.variables])
        st.dataframe(var_df, use_container_width=True, hide_index=True)

    # ── Tag Wizard ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🧙 Tag Creation Wizard")
    st.caption("Create a GA4 Event tag step-by-step. Export as JSON to merge into GTM, or push live via the API.")

    # Measure ID hint
    existing_measure_ids = []
    for t in tags_to_show:
        for p in t.get("parameter",[]):
            if p.get("key") in ("tagId","measurementId") and "G-" in str(p.get("value","")):
                existing_measure_ids.append(p["value"])
    hint_id = existing_measure_ids[0] if existing_measure_ids else ""

    # Step indicator
    step = st.session_state.wizard_step
    step_labels = ["1 · Tag Info", "2 · Event Config", "3 · Review & Export"]
    cols = st.columns(3)
    for i, (col, label) in enumerate(zip(cols, step_labels)):
        if i + 1 == step:
            col.markdown(f"**🔵 {label}**")
        elif i + 1 < step:
            col.markdown(f"✅ ~~{label}~~")
        else:
            col.markdown(f"⬜ {label}")

    st.markdown("---")

    if step == 1:
        with st.form("wiz_step1"):
            tag_name = st.text_input("Tag Name", placeholder="GA4 – Contact Form Submit",
                                     value=st.session_state.wizard_data.get("name",""))
            measure_id = st.text_input("GA4 Measurement ID",
                                       placeholder=hint_id or "G-XXXXXXXXXX",
                                       value=st.session_state.wizard_data.get("measurement_id", hint_id))
            submitted = st.form_submit_button("Next →")
            if submitted:
                if not tag_name:
                    st.error("Tag name is required.")
                elif manager.check_exists(tag_name):
                    st.warning(f"⚠️ A tag named '{tag_name}' already exists in your loaded container.")
                elif not re.match(r"^G-[A-Z0-9]+$", measure_id):
                    st.warning("Measurement ID should be in format G-XXXXXXXXXX")
                else:
                    st.session_state.wizard_data.update({"name": tag_name, "measurement_id": measure_id})
                    st.session_state.wizard_step = 2
                    st.rerun()

    elif step == 2:
        with st.form("wiz_step2"):
            event_name = st.text_input("GA4 Event Name",
                                       placeholder="generate_lead",
                                       value=st.session_state.wizard_data.get("event_name",""))
            st.caption("Common GA4 events: `generate_lead`, `form_submit`, `file_download`, `sign_up`, `purchase`")

            form_id_param = st.text_input("Form ID parameter (optional)",
                                          placeholder="{{dlv - form_id}}",
                                          value=st.session_state.wizard_data.get("form_id",""))

            # Trigger dropdown
            trig_opts = {"— No trigger (add manually) —": ""}
            for tr in triggers_to_show:
                trig_opts[tr["name"]] = tr["triggerId"]
            trig_name_sel = st.selectbox("Firing Trigger", list(trig_opts.keys()),
                                          key="wiz_trigger")
            trig_id_sel = trig_opts[trig_name_sel]

            submitted = st.form_submit_button("Review →")
            if submitted:
                if not event_name:
                    st.error("Event name is required.")
                else:
                    st.session_state.wizard_data.update({
                        "event_name": event_name,
                        "form_id": form_id_param,
                        "trigger_id": trig_id_sel,
                        "trigger_name": trig_name_sel,
                    })
                    st.session_state.wizard_step = 3
                    st.rerun()

        if st.button("← Back"):
            st.session_state.wizard_step = 1
            st.rerun()

    elif step == 3:
        data = st.session_state.wizard_data
        st.markdown("### ✅ Configuration Summary")

        summary = {
            "Tag Name":        data.get("name",""),
            "Measurement ID":  data.get("measurement_id",""),
            "Event Name":      data.get("event_name",""),
            "Form ID Param":   data.get("form_id","") or "—",
            "Firing Trigger":  data.get("trigger_name","") or "None",
        }
        st.table(pd.DataFrame({"Setting": summary.keys(), "Value": summary.values()}))

        tag_body_local = manager.export_json(data)
        tag_body_api   = manager.generate_tag_body(data, for_api=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button(
                label="⬇️ Export JSON (merge into GTM)",
                data=json.dumps(tag_body_local, indent=2),
                file_name=f"gtm_tag_{data.get('name','new_tag').replace(' ','_')}.json",
                mime="application/json",
            )
        with col_b:
            if st.session_state.api_connected and st.session_state.gtm_workspaces:
                ws_ids = {ws["name"]: ws["workspaceId"]
                          for ws in st.session_state.gtm_workspaces}
                ws_push = st.selectbox("Push to workspace", list(ws_ids.keys()), key="ws_push")
                if st.button("🚀 Push Tag to GTM Live"):
                    with st.spinner("Creating tag…"):
                        result = gtm_create_tag(
                            st.session_state.get("cred_acc",""),
                            st.session_state.get("cred_con",""),
                            ws_ids[ws_push],
                            st.session_state.gtm_token,
                            tag_body_api,
                        )
                    if result:
                        st.success(f"✅ Tag '{result.get('name')}' created in GTM! Tag ID: {result.get('tagId')}")
                        # Refresh live tags
                        st.session_state.gtm_live_tags = gtm_list_tags(
                            st.session_state.get("cred_acc",""),
                            st.session_state.get("cred_con",""),
                            ws_ids[ws_push],
                            st.session_state.gtm_token,
                        )
            else:
                st.info("Connect via the sidebar to push tags live to GTM.")

        st.markdown("---")
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("← Back"):
                st.session_state.wizard_step = 2
                st.rerun()
        with bc2:
            if st.button("🔄 Create Another Tag"):
                st.session_state.wizard_step = 1
                st.session_state.wizard_data = {}
                st.rerun()

# ─── FOOTER ──────────────────────────────────────────────────────────────────
st.divider()
st.caption("Marketing Ops Console · Beite.co / Privacy Trust · Built with Streamlit + Plotly")
