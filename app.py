"""
PrivacyTrust Marketing Operations Console
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import json
import uuid
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PrivacyTrust | Marketing Ops Console",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── THEME / GLOBAL CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
/* Tighten Streamlit default padding */
.block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #f8f9fc;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    padding: 14px 18px;
}
[data-testid="metric-container"] label { font-size: 11px !important; text-transform: uppercase; letter-spacing: .06em; color: #6b7280; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 600; }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #e8eaf0; }
.stTabs [data-baseweb="tab"] { font-size: 13px; padding: 8px 18px; border-radius: 6px 6px 0 0; }

/* Tag cards */
.tag-card {
    background: #fff;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.tag-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: .04em;
    margin-bottom: 6px;
}
.badge-ga4   { background: #dbeafe; color: #1e40af; }
.badge-ads   { background: #fef3c7; color: #92400e; }
.badge-html  { background: #dcfce7; color: #166534; }
.badge-other { background: #f3f4f6; color: #374151; }

/* Section headers */
.section-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #6b7280;
    margin: 1.2rem 0 .6rem;
}

/* Insight box */
.insight-box {
    background: #f0f9ff;
    border-left: 3px solid #0284c7;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    font-size: 12.5px;
    color: #0c4a6e;
    margin-bottom: 12px;
    line-height: 1.6;
}
.insight-warn {
    background: #fff7ed;
    border-left-color: #ea580c;
    color: #7c2d12;
}
.insight-good {
    background: #f0fdf4;
    border-left-color: #16a34a;
    color: #14532d;
}

/* Channel table */
.ch-table { width: 100%; font-size: 12px; border-collapse: collapse; }
.ch-table th { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; padding: 6px 8px; border-bottom: 1px solid #e8eaf0; text-align: left; }
.ch-table td { padding: 7px 8px; border-bottom: 1px solid #f3f4f6; color: #111827; }
.ch-table tr:last-child td { border-bottom: none; }
.bar-mini { height: 4px; border-radius: 2px; background: #3b82f6; display: inline-block; }

/* Trigger pill */
.trigger-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #f8f9fc;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    margin-bottom: 6px;
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

# ── COLOUR PALETTE (consistent across all charts) ────────────────────────────
PALETTE = {
    "primary":    "#3b82f6",
    "success":    "#10b981",
    "warning":    "#f59e0b",
    "danger":     "#ef4444",
    "purple":     "#8b5cf6",
    "teal":       "#06b6d4",
    "channels":   ["#3b82f6","#10b981","#f59e0b","#8b5cf6","#06b6d4","#f97316","#ec4899"],
    "event_sys":  "#93c5fd",
    "event_beh":  "#6ee7b7",
    "event_conv": "#fca5a5",
}

PLOTLY_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", size=12, color="#374151"),
    margin=dict(l=10, r=10, t=36, b=10),
    hoverlabel=dict(bgcolor="white", font_size=12, bordercolor="#e8eaf0"),
)

# ── HELPERS ──────────────────────────────────────────────────────────────────
def parse_ga4_csv(file):
    if file:
        try:
            return pd.read_csv(file, skiprows=9)
        except Exception:
            return None
    return None

def fmt_num(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(int(n))

def tag_badge_class(tag_type):
    if tag_type in ("gaawe", "googtag"): return "badge-ga4", "GA4"
    if tag_type == "awct":               return "badge-ads", "G Ads"
    if tag_type == "html":               return "badge-html", "HTML"
    if tag_type == "gclidw":             return "badge-other", "Linker"
    return "badge-other", tag_type.upper()

def get_tag_trigger_name(tag, triggers):
    ids = tag.get("firingTriggerId", [])
    names = []
    for tid in ids:
        if tid == "2147479553": names.append("All Pages")
        elif tid == "2147479573": names.append("Initialization")
        else:
            match = next((t["name"] for t in triggers if t["triggerId"] == tid), None)
            if match: names.append(match)
    return ", ".join(names) if names else "—"

# ── GTM PARSER ───────────────────────────────────────────────────────────────
class GTMInspector:
    def __init__(self, data=None):
        self.data = data or {}
        self.cv   = self.data.get("containerVersion", {})
        self.tags      = self.cv.get("tag", [])
        self.triggers  = self.cv.get("trigger", [])
        self.variables = self.cv.get("variable", [])
        self.built_in  = self.cv.get("builtInVariable", [])

    def tag_exists(self, name):
        return any(t["name"].lower() == name.lower() for t in self.tags)

    def generate_tag_json(self, config):
        return {
            "exportFormatVersion": 2,
            "containerVersion": {
                "tag": [{
                    "name": config["name"],
                    "type": "gaawe",
                    "parameter": [
                        {"type": "TEMPLATE", "key": "eventName",            "value": config["event_name"]},
                        {"type": "TEMPLATE", "key": "measurementIdOverride", "value": config["target_id"]}
                    ],
                    "fingerprint": str(uuid.uuid4())
                }]
            }
        }

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔐 PrivacyTrust")
    st.caption("Marketing Operations Console")
    st.divider()

    st.subheader("📁 Data Uploads")
    up_traffic = st.file_uploader("Traffic Acquisition CSV", type="csv")
    up_pages   = st.file_uploader("Pages & Screens CSV",     type="csv")
    up_events  = st.file_uploader("Events CSV",              type="csv")
    up_gtm     = st.file_uploader("GTM Container JSON",      type="json")

    st.divider()
    with st.expander("⚙️ Console Settings", expanded=False):
        org_name = st.text_input("Organization", value="PrivacyTrust")
        prop_label = st.text_input("Property", value="privacytrust.sg")
        top_n_pages = st.slider("Top N Pages to show", 10, 30, 15)

# ── DATA LOAD ─────────────────────────────────────────────────────────────────
df_traffic = parse_ga4_csv(up_traffic)
df_pages   = parse_ga4_csv(up_pages)
df_events  = parse_ga4_csv(up_events)
gtm_raw    = json.load(up_gtm) if up_gtm else None
gtm        = GTMInspector(gtm_raw)

# ── HEADER ───────────────────────────────────────────────────────────────────
hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown(f"## {org_name} — Marketing Ops Console")
    st.caption(f"Property: **{prop_label}** · Apr 2022 – May 2026 · GTM: GTM-TQMH8PHV")
with hcol2:
    if gtm_raw:
        st.success(f"✅ GTM v8 loaded · {len(gtm.tags)} tags")
    else:
        st.warning("No GTM JSON loaded")

# ── TABS ──────────────────────────────────────────────────────────────────────
tab_ana, tab_pages, tab_conv, tab_gtm, tab_wiz = st.tabs([
    "📊 Analytics",
    "📄 Top Pages",
    "🎯 Conversions",
    "🔍 GTM Inspector",
    "🧙 Tag Wizard",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ana:
    if df_traffic is not None:
        # Rename columns for safety
        col_map = {
            df_traffic.columns[0]: "channel",
            df_traffic.columns[1]: "sessions",
            df_traffic.columns[2]: "engaged_sessions",
            df_traffic.columns[3]: "engagement_rate",
            df_traffic.columns[4]: "avg_engagement_time",
            df_traffic.columns[5]: "events_per_session",
            df_traffic.columns[6]: "event_count",
            df_traffic.columns[7]: "key_events",
        }
        df = df_traffic.rename(columns=col_map).copy()

        # Channel filter
        with st.container(border=True):
            all_channels = df["channel"].tolist()
            sel = st.multiselect("Filter channels", all_channels, default=all_channels, label_visibility="collapsed")
        df_f = df[df["channel"].isin(sel)]

        # ── KPI ROW ──
        total_sessions  = int(df_f["sessions"].sum())
        total_events    = int(df_events.iloc[:, 1].sum()) if df_events is not None else 0
        avg_eng_rate    = df_f["engagement_rate"].mean()
        avg_eng_time    = df_f["avg_engagement_time"].mean()
        key_ev          = int(df_f["key_events"].sum())

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Sessions",    fmt_num(total_sessions))
        k2.metric("Engaged Sessions",  fmt_num(int(df_f["engaged_sessions"].sum())))
        k3.metric("Avg Engagement",    f"{avg_eng_rate:.1%}")
        k4.metric("Key Events",        fmt_num(key_ev), help="generate_lead conversions")
        k5.metric("Total Events",      fmt_num(total_events))

        st.markdown("<div class='insight-box'>💡 <strong>Direct</strong> dominates at 58.8% of sessions but has the <strong>lowest engagement rate (35%)</strong> — likely branded/returning traffic. <strong>Paid Search</strong> drives the highest engagement time at 65.7s/session despite only 1.5% of sessions, suggesting high-intent visitors. <strong>Display</strong> has near-zero engagement time (0.05s) — those sessions are essentially bounces.</div>", unsafe_allow_html=True)

        # ── CHARTS ROW 1: Acquisition + Engagement Rate ──
        c1, c2 = st.columns(2)

        with c1:
            fig_pie = px.pie(
                df_f, values="sessions", names="channel",
                title="Acquisition Share by Sessions",
                color_discrete_sequence=PALETTE["channels"],
                hole=0.42,
            )
            fig_pie.update_traces(
                textposition="outside",
                textinfo="percent+label",
                textfont_size=11,
                pull=[0.03]*len(df_f),
            )
            fig_pie.update_layout(
                **PLOTLY_BASE,
                showlegend=False,
                height=320,
                title_font_size=13,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with c2:
            df_eng = df_f.sort_values("engagement_rate", ascending=True)
            fig_eng = px.bar(
                df_eng, x="engagement_rate", y="channel",
                orientation="h",
                title="Engagement Rate by Channel",
                text=df_eng["engagement_rate"].apply(lambda x: f"{x:.0%}"),
                color="engagement_rate",
                color_continuous_scale=["#bfdbfe","#1d4ed8"],
            )
            fig_eng.update_traces(textposition="outside", textfont_size=11)
            fig_eng.update_layout(
                **PLOTLY_BASE,
                height=320,
                title_font_size=13,
                coloraxis_showscale=False,
                xaxis=dict(tickformat=".0%", showgrid=True, gridcolor="#f3f4f6"),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig_eng, use_container_width=True)

        # ── CHART: Avg Engagement Time ──
        df_time = df_f.sort_values("avg_engagement_time", ascending=True)
        colors_time = [PALETTE["danger"] if v < 10 else PALETTE["warning"] if v < 40 else PALETTE["success"]
                       for v in df_time["avg_engagement_time"]]
        fig_time = go.Figure(go.Bar(
            x=df_time["avg_engagement_time"],
            y=df_time["channel"],
            orientation="h",
            marker_color=colors_time,
            text=[f"{v:.1f}s" for v in df_time["avg_engagement_time"]],
            textposition="outside",
        ))
        fig_time.update_layout(
            **PLOTLY_BASE,
            title="Avg Engagement Time per Session (seconds)",
            title_font_size=13,
            height=240,
            xaxis=dict(title="seconds", showgrid=True, gridcolor="#f3f4f6"),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_time, use_container_width=True)

        # ── CHANNEL TABLE ──
        st.markdown("<div class='section-header'>Channel breakdown</div>", unsafe_allow_html=True)
        max_sess = df_f["sessions"].max()
        rows = ""
        for _, r in df_f.sort_values("sessions", ascending=False).iterrows():
            bar_w = int(r["sessions"] / max_sess * 80)
            rows += f"""<tr>
                <td><strong>{r['channel']}</strong></td>
                <td>{r['sessions']:,} <span class='bar-mini' style='width:{bar_w}px'></span></td>
                <td>{r['engaged_sessions']:,}</td>
                <td>{r['engagement_rate']:.1%}</td>
                <td>{r['avg_engagement_time']:.1f}s</td>
                <td>{r['event_count']:,}</td>
                <td>{int(r['key_events'])}</td>
            </tr>"""
        st.markdown(f"""
        <table class='ch-table'>
          <thead><tr>
            <th>Channel</th><th>Sessions</th><th>Engaged</th>
            <th>Eng. Rate</th><th>Avg Time</th><th>Events</th><th>Key Events</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>""", unsafe_allow_html=True)

        # ── EVENTS CHART ──
        if df_events is not None:
            st.markdown("<div class='section-header'>Event activity</div>", unsafe_allow_html=True)

            ev_col = {
                df_events.columns[0]: "event",
                df_events.columns[1]: "count",
                df_events.columns[2]: "users",
            }
            df_ev = df_events.rename(columns=ev_col).copy()

            # Categorise events
            sys_events  = ["page_view","GA Configuration","session_start","first_visit","user_engagement"]
            conv_events = ["generate_lead","form_submit","form_start","key_event"]

            def ev_color(name):
                if name in sys_events:  return PALETTE["event_sys"]
                if name in conv_events: return PALETTE["event_conv"]
                return PALETTE["event_beh"]

            df_ev_top = df_ev.head(14).sort_values("count", ascending=True)
            df_ev_top["color"] = df_ev_top["event"].apply(ev_color)

            fig_ev = go.Figure(go.Bar(
                x=df_ev_top["count"],
                y=df_ev_top["event"],
                orientation="h",
                marker_color=df_ev_top["color"],
                text=[fmt_num(v) for v in df_ev_top["count"]],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Count: %{x:,}<extra></extra>",
            ))
            fig_ev.update_layout(
                **PLOTLY_BASE,
                title="Top Events by Count — colour: 🔵 system · 🟢 behaviour · 🔴 conversion",
                title_font_size=13,
                height=420,
                xaxis=dict(showgrid=True, gridcolor="#f3f4f6"),
                yaxis=dict(showgrid=False, tickfont_size=11),
            )
            st.plotly_chart(fig_ev, use_container_width=True)

            st.markdown("<div class='insight-warn'>⚠️ <strong>GA Configuration</strong> appearing as an event (16,538 times) confirms the old duplicate GA4 tag was firing — this is the ghost event from the removed tag. It will disappear from new data after v8 is published.</div>", unsafe_allow_html=True)

    else:
        st.info("⬆️ Upload your **Traffic Acquisition CSV** from GA4 to populate this tab.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — TOP PAGES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_pages:
    if df_pages is not None:
        pcol = {
            df_pages.columns[0]: "path",
            df_pages.columns[1]: "views",
            df_pages.columns[2]: "users",
            df_pages.columns[3]: "views_per_user",
            df_pages.columns[4]: "avg_eng_time",
            df_pages.columns[5]: "event_count",
            df_pages.columns[6]: "key_events",
        }
        dp = df_pages.rename(columns=pcol).copy()

        # Clean: remove wp-content/wp-admin noise
        noise = ["wp-content","wp-admin","cache.aspx",".png",".webp",".jpg","wpfd_file","wpfunnel"]
        dp_clean = dp[~dp["path"].apply(lambda x: any(n in x for n in noise))].copy()

        # Shorten path labels
        def short_path(p):
            p = p.strip("/")
            if p == "": return "/ (homepage)"
            parts = p.split("/")
            if len(parts) > 2: return "/" + "/".join(parts[:2]) + "/…"
            return "/" + p

        dp_clean["label"] = dp_clean["path"].apply(short_path)

        # ── PAGE KPIs ──
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Top Page Views",      f"{dp_clean['views'].iloc[0]:,}",   help=dp_clean['path'].iloc[0])
        p2.metric("Highest Key Events",  f"{dp_clean['key_events'].max():,}", help="/contact-us/")
        p3.metric("Best Engagement Time",f"{dp_clean['avg_eng_time'].max():.0f}s",
                  help=dp_clean.loc[dp_clean['avg_eng_time'].idxmax(),'path'])
        p4.metric("Unique Pages Tracked",f"{len(dp_clean):,}")

        st.markdown("<div class='insight-good'>✅ <strong>/contact-us/</strong> is the star conversion page — 751 views, 392 key events (52% conversion rate). <strong>/lp1-hc-hib-2/</strong> has exceptional engagement at 119s/session with a very targeted audience (36 users) — likely a high-intent healthcare landing page worth scaling.</div>", unsafe_allow_html=True)

        # ── TOP PAGES BAR ──
        dp_top = dp_clean.head(top_n_pages).sort_values("views", ascending=True)
        fig_pages = go.Figure(go.Bar(
            x=dp_top["views"],
            y=dp_top["label"],
            orientation="h",
            marker=dict(
                color=dp_top["key_events"],
                colorscale=[[0,"#bfdbfe"],[0.5,"#3b82f6"],[1,"#1e40af"]],
                colorbar=dict(title="Key Events", thickness=12, len=0.6),
                showscale=True,
            ),
            text=[f"{v:,}" for v in dp_top["views"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Views: %{x:,}<br>Key Events: %{marker.color}<extra></extra>",
        ))
        fig_pages.update_layout(
            **PLOTLY_BASE,
            title=f"Top {top_n_pages} Pages — Views (colour intensity = Key Events)",
            title_font_size=13,
            height=max(420, top_n_pages * 28),
            xaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Views"),
            yaxis=dict(showgrid=False, tickfont_size=10),
            margin=dict(l=10, r=80, t=36, b=10),
        )
        st.plotly_chart(fig_pages, use_container_width=True)

        # ── SCATTER: Views vs Engagement Time ──
        dp_scatter = dp_clean[dp_clean["views"] >= 20].head(30).copy()
        dp_scatter["key_events_sized"] = dp_scatter["key_events"].clip(lower=1)

        fig_sc = px.scatter(
            dp_scatter,
            x="views",
            y="avg_eng_time",
            size="key_events_sized",
            color="key_events",
            hover_name="path",
            text="label",
            color_continuous_scale=["#bfdbfe","#1d4ed8"],
            title="Views vs Avg Engagement Time — bubble size = Key Events",
            labels={"views":"Page Views","avg_eng_time":"Avg Engagement Time (s)","key_events":"Key Events"},
            size_max=40,
        )
        fig_sc.update_traces(
            textposition="top center",
            textfont=dict(size=9, color="#374151"),
            marker=dict(line=dict(width=1, color="#fff")),
        )
        fig_sc.update_layout(
            **PLOTLY_BASE,
            height=480,
            title_font_size=13,
            coloraxis_colorbar=dict(title="Key Events", thickness=12),
            xaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Page Views"),
            yaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Avg Engagement Time (s)"),
        )
        st.plotly_chart(fig_sc, use_container_width=True)
        st.caption("💡 Top-right quadrant = high views + high engagement = your best content. Top-left = hidden gems (high engagement, low traffic — candidates to promote).")

        # ── VIEWS PER USER (content stickiness) ──
        dp_sticky = dp_clean[dp_clean["views"] >= 30].sort_values("views_per_user", ascending=False).head(15)
        fig_stick = px.bar(
            dp_sticky.sort_values("views_per_user", ascending=True),
            x="views_per_user", y="label",
            orientation="h",
            title="Content Stickiness — Views per Active User (top pages with 30+ views)",
            color="views_per_user",
            color_continuous_scale=["#d1fae5","#065f46"],
            text=dp_sticky.sort_values("views_per_user", ascending=True)["views_per_user"].apply(lambda x: f"{x:.1f}x"),
        )
        fig_stick.update_traces(textposition="outside")
        fig_stick.update_layout(
            **PLOTLY_BASE,
            height=380,
            title_font_size=13,
            coloraxis_showscale=False,
            xaxis=dict(showgrid=True, gridcolor="#f3f4f6", title="Views / User"),
            yaxis=dict(showgrid=False, tickfont_size=10),
        )
        st.plotly_chart(fig_stick, use_container_width=True)

    else:
        st.info("⬆️ Upload your **Pages & Screens CSV** from GA4 to populate this tab.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CONVERSIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_conv:
    if df_events is not None and df_traffic is not None:
        ev_col2 = {df_events.columns[0]:"event", df_events.columns[1]:"count", df_events.columns[2]:"users"}
        df_ev2 = df_events.rename(columns=ev_col2).copy()

        total_sess = df_traffic.rename(columns={df_traffic.columns[1]:"sessions"})["sessions"].sum()

        gen_lead   = df_ev2[df_ev2["event"]=="generate_lead"]["count"].sum()
        form_sub   = df_ev2[df_ev2["event"]=="form_submit"]["count"].sum()
        form_start = df_ev2[df_ev2["event"]=="form_start"]["count"].sum()
        downloads  = df_ev2[df_ev2["event"]=="file_download"]["count"].sum()

        conv_rate = gen_lead / total_sess if total_sess else 0
        form_completion = form_sub / form_start if form_start else 0

        cv1, cv2, cv3, cv4 = st.columns(4)
        cv1.metric("Lead Conversions",    f"{int(gen_lead):,}")
        cv2.metric("Session→Lead Rate",   f"{conv_rate:.2%}")
        cv3.metric("Form Completion Rate",f"{form_completion:.1%}", help="form_submit / form_start")
        cv4.metric("File Downloads",      f"{int(downloads):,}")

        st.markdown(f"<div class='insight-good'>✅ <strong>{int(gen_lead):,} generate_lead events</strong> recorded across {int(total_sess):,} sessions — a {conv_rate:.2%} session-to-lead rate. Form completion is <strong>{form_completion:.1%}</strong> ({int(form_sub)} submitted out of {int(form_start)} started) — room to optimise form UX.</div>", unsafe_allow_html=True)

        # Funnel
        funnel_stages = ["Sessions", "Form Starts", "Form Submits", "Generate Lead"]
        funnel_values = [int(total_sess), int(form_start), int(form_sub), int(gen_lead)]

        fig_funnel = go.Figure(go.Funnel(
            y=funnel_stages,
            x=funnel_values,
            textinfo="value+percent initial",
            marker=dict(color=["#3b82f6","#6366f1","#10b981","#f59e0b"]),
            connector=dict(line=dict(color="#e8eaf0", width=2)),
        ))
        fig_funnel.update_layout(
            **PLOTLY_BASE,
            title="Conversion Funnel — Sessions → Lead",
            title_font_size=13,
            height=340,
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

        # Conversion events breakdown
        conv_events_list = ["generate_lead","form_submit","form_start","file_download","click","view_search_results"]
        df_conv_ev = df_ev2[df_ev2["event"].isin(conv_events_list)].sort_values("count", ascending=False)

        fig_conv_bar = px.bar(
            df_conv_ev,
            x="event", y="count",
            title="Conversion-Signal Events",
            color="event",
            color_discrete_sequence=PALETTE["channels"],
            text="count",
        )
        fig_conv_bar.update_traces(textposition="outside")
        fig_conv_bar.update_layout(
            **PLOTLY_BASE,
            height=320,
            title_font_size=13,
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#f3f4f6"),
        )
        st.plotly_chart(fig_conv_bar, use_container_width=True)

        # Conversion by channel
        if df_traffic is not None:
            tcol = {df_traffic.columns[0]:"channel", df_traffic.columns[7]:"key_events", df_traffic.columns[1]:"sessions", df_traffic.columns[8]:"key_event_rate"}
            df_tc = df_traffic.rename(columns=tcol)[["channel","sessions","key_events","key_event_rate"]].copy()
            df_tc = df_tc[df_tc["key_events"] > 0].sort_values("key_events", ascending=False)

            fig_ch_conv = px.bar(
                df_tc, x="channel", y="key_events",
                color="key_event_rate",
                color_continuous_scale=["#bfdbfe","#1d4ed8"],
                title="Key Events by Channel — colour = key event rate",
                text="key_events",
            )
            fig_ch_conv.update_traces(textposition="outside")
            fig_ch_conv.update_layout(
                **PLOTLY_BASE,
                height=320,
                title_font_size=13,
                coloraxis_colorbar=dict(title="Key Event Rate", tickformat=".1%", thickness=12),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#f3f4f6"),
            )
            st.plotly_chart(fig_ch_conv, use_container_width=True)
            st.markdown("<div class='insight-box'>💡 <strong>Direct</strong> and <strong>Organic Search</strong> drive almost all conversions. Paid Search has 0 key events despite a high engagement time — the campaign may not be driving users to the conversion page. Consider a dedicated landing page with a visible form for Paid Search traffic.</div>", unsafe_allow_html=True)

    else:
        st.info("⬆️ Upload both **Events CSV** and **Traffic CSV** to view conversion analysis.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — GTM INSPECTOR
# ═══════════════════════════════════════════════════════════════════════════════
with tab_gtm:
    if gtm_raw:
        # Summary metrics
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Tags",           len(gtm.tags))
        g2.metric("Triggers",       len(gtm.triggers))
        g3.metric("Variables",      len(gtm.variables))
        g4.metric("Built-in Vars",  len(gtm.built_in))

        # ── TAGS GRID ──
        st.markdown("<div class='section-header'>Tags — click to inspect</div>", unsafe_allow_html=True)

        cols_per_row = 2
        tag_cols = st.columns(cols_per_row)
        selected_tag = st.session_state.get("sel_tag", None)

        for i, tag in enumerate(gtm.tags):
            badge_cls, badge_label = tag_badge_class(tag["type"])
            trigger_name = get_tag_trigger_name(tag, gtm.triggers)
            with tag_cols[i % cols_per_row]:
                st.markdown(f"""
                <div class='tag-card'>
                  <span class='tag-badge {badge_cls}'>{badge_label}</span>
                  <div style='font-size:13px;font-weight:600;color:#111827;margin-bottom:4px'>{tag['name']}</div>
                  <div style='font-size:11px;color:#6b7280'>Fires on: {trigger_name}</div>
                </div>""", unsafe_allow_html=True)

        # Tag detail viewer
        st.markdown("<div class='section-header'>Tag detail inspector</div>", unsafe_allow_html=True)
        tag_names_list = [t["name"] for t in gtm.tags]
        sel = st.selectbox("Select a tag to inspect", ["— select —"] + tag_names_list)
        if sel != "— select —":
            tag_obj = next(t for t in gtm.tags if t["name"] == sel)
            col_j1, col_j2 = st.columns([1, 2])
            with col_j1:
                badge_cls, badge_label = tag_badge_class(tag_obj["type"])
                trigger_name = get_tag_trigger_name(tag_obj, gtm.triggers)
                st.markdown(f"""
                <div class='tag-card'>
                  <span class='tag-badge {badge_cls}'>{badge_label}</span>
                  <div style='font-size:14px;font-weight:600;margin:6px 0 4px'>{tag_obj['name']}</div>
                  <div style='font-size:12px;color:#6b7280'>Type: <code>{tag_obj['type']}</code></div>
                  <div style='font-size:12px;color:#6b7280;margin-top:4px'>Fires on: {trigger_name}</div>
                </div>""", unsafe_allow_html=True)
            with col_j2:
                st.json(tag_obj)

        # ── TRIGGERS ──
        st.markdown("<div class='section-header'>Triggers</div>", unsafe_allow_html=True)
        type_colors = {
            "FORM_SUBMISSION": ("#EAF3DE","#166534","📋"),
            "SCROLL_DEPTH":    ("#EEEDFE","#4c1d95","📜"),
            "LINK_CLICK":      ("#FAEEDA","#92400e","🔗"),
            "PAGE_VIEW":       ("#dbeafe","#1e40af","📄"),
            "CUSTOM_EVENT":    ("#FAECE7","#7c2d12","⚡"),
        }
        for trig in gtm.triggers:
            ttype = trig.get("type","")
            bg, fg, icon = type_colors.get(ttype, ("#f3f4f6","#374151","◆"))
            filters_desc = ""
            for f in trig.get("filter", [])[:2]:
                arg1 = next((p["value"] for p in f["parameter"] if p["key"]=="arg1"), "")
                filters_desc += f" · {f['type']}: <code>{arg1}</code>"
            st.markdown(f"""
            <div class='trigger-pill'>
              <span style='background:{bg};color:{fg};border-radius:6px;padding:4px 8px;font-size:11px;font-weight:600'>{icon} {ttype}</span>
              <span style='font-weight:600;color:#111827;font-size:12px'>{trig['name']}</span>
              <span style='font-size:11px;color:#6b7280;margin-left:auto'>{filters_desc}</span>
            </div>""", unsafe_allow_html=True)

        # ── VARIABLES ──
        st.markdown("<div class='section-header'>User-defined variables</div>", unsafe_allow_html=True)
        vcols = st.columns(2)
        for i, var in enumerate(gtm.variables):
            val = next((p["value"] for p in var.get("parameter",[]) if p["key"]=="value"), "—")
            with vcols[i % 2]:
                st.markdown(f"""
                <div class='tag-card'>
                  <div style='font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px'>Constant · {var['type']}</div>
                  <div style='font-size:13px;font-weight:600;color:#111827'>{var['name']}</div>
                  <div style='font-family:monospace;font-size:12px;color:#0284c7;margin-top:4px'>{val}</div>
                </div>""", unsafe_allow_html=True)

    else:
        st.warning("⬆️ Upload the **GTM Container JSON (v8)** in the sidebar to use the inspector.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — TAG WIZARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_wiz:
    st.subheader("GA4 Event Tag Wizard")
    st.caption("Create a GTM-importable GA4 event tag JSON in 3 steps.")

    if "wiz_step" not in st.session_state:
        st.session_state.wiz_step = 1
        st.session_state.wiz_data = {}

    # Progress indicator
    prog_labels = ["1 · Identity", "2 · Event", "3 · Export"]
    p1, p2, p3 = st.columns(3)
    for col, label, step in zip([p1,p2,p3], prog_labels, [1,2,3]):
        active = st.session_state.wiz_step == step
        done   = st.session_state.wiz_step > step
        col.markdown(f"""
        <div style='text-align:center;padding:8px;border-radius:8px;
             background:{"#dbeafe" if active else "#f0fdf4" if done else "#f3f4f6"};
             color:{"#1e40af" if active else "#166534" if done else "#6b7280"};
             font-size:12px;font-weight:{"600" if active else "400"}'>
          {"✅ " if done else ""}{label}
        </div>""", unsafe_allow_html=True)

    st.divider()

    if st.session_state.wiz_step == 1:
        st.markdown("**Step 1 — Tag identity**")
        name = st.text_input("New Tag Name", placeholder="GA4 - Event - My Custom Event")
        tid  = st.text_input("GA4 Measurement ID", placeholder="G-XXXXXXXXXX",
                             value="{{GA4 Measurement ID}}")
        if st.button("Next →", type="primary"):
            if gtm and gtm.tag_exists(name):
                st.error(f"⚠️ A tag named '{name}' already exists in the loaded container.")
            elif not name or not tid:
                st.error("Please fill in both fields.")
            else:
                st.session_state.wiz_data.update({"name": name, "target_id": tid})
                st.session_state.wiz_step = 2
                st.rerun()

    elif st.session_state.wiz_step == 2:
        st.markdown("**Step 2 — GA4 event config**")
        event = st.text_input("GA4 Event Name", placeholder="e.g. webinar_registration")
        st.caption("Use snake_case. This is the event name that appears in GA4 reports.")
        col_back, col_next = st.columns([1,4])
        with col_back:
            if st.button("← Back"):
                st.session_state.wiz_step = 1
                st.rerun()
        with col_next:
            if st.button("Review →", type="primary"):
                if not event:
                    st.error("Enter a GA4 event name.")
                else:
                    st.session_state.wiz_data["event_name"] = event
                    st.session_state.wiz_step = 3
                    st.rerun()

    elif st.session_state.wiz_step == 3:
        st.markdown("**Step 3 — Review & export**")
        d = st.session_state.wiz_data
        st.table(pd.DataFrame({
            "Field": ["Tag Name","Measurement ID","GA4 Event Name"],
            "Value": [d.get("name",""), d.get("target_id",""), d.get("event_name","")]
        }).set_index("Field"))

        out = gtm.generate_tag_json(d)
        json_str = json.dumps(out, indent=2)

        col_dl, col_rst, col_back = st.columns([2,1,1])
        with col_dl:
            st.download_button(
                "⬇️ Download GTM JSON",
                data=json_str,
                file_name=f"gtm_tag_{d.get('event_name','new')}.json",
                mime="application/json",
                type="primary",
            )
        with col_rst:
            if st.button("🔄 Start Over"):
                st.session_state.wiz_step = 1
                st.session_state.wiz_data = {}
                st.rerun()
        with col_back:
            if st.button("← Back"):
                st.session_state.wiz_step = 2
                st.rerun()

        with st.expander("Preview JSON"):
            st.code(json_str, language="json")
        st.info("Import this JSON into GTM using **Admin → Import Container → Merge**. Then add your firing trigger manually.")
