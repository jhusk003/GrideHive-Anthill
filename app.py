"""GridHive - the Anthill V3.
Synthetic HackSTEM hurricane-resilience demonstration.
No live utility data or autonomous grid control.
"""

from __future__ import annotations

import math
import os
import sqlite3
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, ImageOps

st.set_page_config(
    page_title="the Anthill | GridHive",
    page_icon="🐞",
    layout="wide"
)

NAVY = "#071724"
PANEL = "#102B3D"
CYAN = "#5CE6E2"
WHITE = "#F3FAFF"
MUTED = "#C9DEEB"
RED = "#FF7A91"
AMBER = "#F7BD67"
GREEN = "#56D9B0"

# ==========================================
# DESIGN / HIGH CONTRAST THEME
# ==========================================

st.markdown("""
<style>
:root {color-scheme: dark;}

.stApp,
[data-testid="stAppViewContainer"] {
    background: #071724;
    color: #F3FAFF;
}

[data-testid="stSidebar"] {
    background: #0B2131;
    border-right: 1px solid #2C5164;
}

.stApp p,
.stApp span,
.stApp label,
.stApp li,
.stApp h1,
.stApp h2,
.stApp h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {
    color: #F3FAFF;
}

[data-testid="stCaptionContainer"],
.stCaption {
    color: #C9DEEB !important;
}

[data-testid="stMetric"] {
    background: #102B3D;
    border: 1px solid #31566A;
    border-radius: 12px;
    padding: 16px;
}

[data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"] * {
    color: #F3FAFF !important;
}

[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
textarea,
[data-testid="stNumberInput"] input {
    background: #153549 !important;
    color: #FFFFFF !important;
    border-color: #61899C !important;
}

input,
textarea,
[role="option"],
[role="listbox"] {
    color: #FFFFFF !important;
}

[data-baseweb="popover"] {
    background: #153549 !important;
}

button[kind="primary"] {
    background: #007E92 !important;
    color: #FFFFFF !important;
    border: 1px solid #6EEAE6 !important;
}

button[kind="secondary"] {
    background: #173B50 !important;
    color: #FFFFFF !important;
    border: 1px solid #739CAF !important;
}

button[kind="primary"] *,
button[kind="secondary"] * {
    color: #FFFFFF !important;
}

button:focus-visible,
input:focus-visible {
    outline: 3px solid #5CE6E2 !important;
}

button[data-baseweb="tab"] {
    color: #D5EAF4 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #5CE6E2 !important;
    border-bottom-color: #5CE6E2 !important;
}

[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border: 1px solid #31566A;
    border-radius: 10px;
}

.hero {
    background: linear-gradient(115deg,#103248,#0B1D2D);
    border: 1px solid #34748A;
    padding: 22px 26px;
    border-radius: 16px;
    margin-bottom: 18px;
}

.hero h1 {
    color: #F3FAFF !important;
    font-size: 2.25rem;
    margin: 0;
}

.hero p {
    color: #C9DEEB !important;
    margin: 5px 0 0;
}

.eyebrow {
    color: #5CE6E2 !important;
    font-weight: 700;
    letter-spacing: .15em;
    font-size: .76rem;
}

.note {
    background: #12374A;
    border-left: 4px solid #5CE6E2;
    padding: 12px 16px;
    border-radius: 8px;
    color: #F3FAFF;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# SYNTHETIC INFRASTRUCTURE DATA
# ==========================================

ASSETS = [
    dict(
        id="S01", name="Miami Demo Substation",
        kind="Substation", parent=None,
        lat=25.780, lon=-80.255, x=1, y=5,
        customers=0, base=19, wind=.95,
        flood=.85, critical=95, hours=10
    ),
    dict(
        id="F01", name="Doral Demo Feeder",
        kind="Feeder", parent="S01",
        lat=25.803, lon=-80.356, x=2, y=6,
        customers=3900, base=23, wind=.83,
        flood=.55, critical=78, hours=6
    ),
    dict(
        id="T01", name="Sweetwater Demo Transformer",
        kind="Transformer", parent="F01",
        lat=25.764, lon=-80.370, x=3, y=7,
        customers=740, base=14, wind=.68,
        flood=.48, critical=65, hours=4
    ),
    dict(
        id="T02", name="Westchester Demo Transformer",
        kind="Transformer", parent="F01",
        lat=25.750, lon=-80.305, x=3, y=5.3,
        customers=620, base=16, wind=.76,
        flood=.58, critical=75, hours=5
    ),
    dict(
        id="F02", name="Little Havana Demo Feeder",
        kind="Feeder", parent="S01",
        lat=25.765, lon=-80.220, x=2, y=3.6,
        customers=3100, base=21, wind=.91,
        flood=.73, critical=86, hours=7
    ),
    dict(
        id="T03", name="Brickell Demo Transformer",
        kind="Transformer", parent="F02",
        lat=25.760, lon=-80.192, x=3, y=3.0,
        customers=890, base=18, wind=.93,
        flood=.95, critical=88, hours=5
    ),
    dict(
        id="S02", name="North Miami Demo Substation",
        kind="Substation", parent=None,
        lat=25.888, lon=-80.205, x=1, y=1.6,
        customers=0, base=15, wind=.89,
        flood=.72, critical=90, hours=11
    ),
    dict(
        id="F03", name="North Miami Demo Feeder",
        kind="Feeder", parent="S02",
        lat=25.899, lon=-80.175, x=2, y=1.7,
        customers=2600, base=17, wind=.87,
        flood=.77, critical=76, hours=6
    ),
    dict(
        id="T04", name="Biscayne Demo Transformer",
        kind="Transformer", parent="F03",
        lat=25.843, lon=-80.178, x=3, y=1.4,
        customers=550, base=15, wind=.92,
        flood=.88, critical=70, hours=4
    )
]

TRACKS = {
    "Miami coast": (25.76, -80.20),
    "Doral / inland": (25.80, -80.36),
    "North Miami": (25.89, -80.20)
}

COLORS = {
    "Critical": RED,
    "Elevated": AMBER,
    "Low": GREEN
}

DB = os.path.join(
    os.path.dirname(__file__),
    "gridhive_demo.sqlite3"
)

# ==========================================
# INSPECTION DATABASE
# ==========================================

def connection():
    db = sqlite3.connect(DB, timeout=8)
    db.execute(
        "CREATE TABLE IF NOT EXISTS inspections "
        "(id INTEGER PRIMARY KEY, "
        "asset_id TEXT NOT NULL, "
        "damage INTEGER NOT NULL, "
        "notes TEXT, photo BLOB, "
        "created TEXT NOT NULL)"
    )
    db.commit()
    return db


def inspections():
    with connection() as db:
        return db.execute(
            "SELECT id,asset_id,damage,notes,photo,created "
            "FROM inspections ORDER BY id DESC LIMIT 50"
        ).fetchall()


def save_inspection(asset_id, damage, notes, photo):
    with connection() as db:
        db.execute(
            "INSERT INTO inspections"
            "(asset_id,damage,notes,photo,created) "
            "VALUES (?,?,?,?,?)",
            (
                asset_id,
                damage,
                notes,
                photo,
                datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
            )
        )
        db.commit()


def reset_inspections():
    with connection() as db:
        db.execute("DELETE FROM inspections")
        db.commit()


def process_photo(upload):
    if upload is None:
        return None

    raw = upload.getvalue()

    if len(raw) > 5_000_000:
        raise ValueError("Photo must be smaller than 5 MB.")

    try:
        with Image.open(BytesIO(raw)) as source:
            if (
                source.format not in ("JPEG", "PNG")
                or source.width * source.height > 12_000_000
            ):
                raise ValueError(
                    "Use a JPEG/PNG smaller than 12 megapixels."
                )

            img = ImageOps.exif_transpose(source)
            img.thumbnail((1200, 1200))

            out = BytesIO()
            img.convert("RGB").save(
                out, "JPEG", quality=83
            )
            return out.getvalue()

    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(
            "Could not read the image safely."
        ) from exc


# ==========================================
# HURRICANE SIMULATION + RESTORATION MODEL
# ==========================================

def model(category, track, faults, records):
    lat0, lon0 = TRACKS[track]

    observed = {}

    for _, asset_id, damage, *_ in records:
        observed[asset_id] = max(
            observed.get(asset_id, 0),
            damage
        )

    nodes = []
    by_id = {}

    for a in ASSETS:
        distance = math.hypot(
            (a["lat"] - lat0) * 111,
            (a["lon"] - lon0) * 100
        )

        exposure = max(0, 1 - distance / 45)

        weather = category * (
            a["wind"] * 4.4 + a["flood"] * 3.6
        ) * (0.28 + 0.72 * exposure)

        risk = min(
            100,
            round(
                max(
                    a["base"] + weather,
                    observed.get(a["id"], 0)
                ),
                1
            )
        )

        failed = bool(
            faults and (
                risk >= 77
                or observed.get(a["id"], 0) >= 85
            )
        )

        parent_outage = bool(
            a["parent"]
            and by_id[a["parent"]]["offline"]
        )

        offline = failed or parent_outage

        band = (
            "Critical" if risk >= 75
            else "Elevated" if risk >= 48
            else "Low"
        )

        node = dict(
            a,
            risk=risk,
            failed=failed,
            offline=offline,
            band=band,
            status=(
                "Direct failure" if failed
                else "Upstream outage" if offline
                else "Energized"
            )
        )

        nodes.append(node)
        by_id[a["id"]] = node

    maximum = max(
        n["customers"] for n in nodes
    ) or 1

    for n in nodes:
        customer_factor = (
            100 * n["customers"] / maximum
        )

        speed_factor = max(
            0,
            100 - 100 * n["hours"] / 18
        )

        n["priority"] = round(
            min(
                100,
                .38 * n["risk"]
                + .25 * customer_factor
                + .27 * n["critical"]
                + .10 * speed_factor
                + (12 if n["failed"] else 0)
            ),
            1
        )

        n["estimated_hours"] = round(
            n["hours"] + category * .45,
            1
        )

    return nodes


# ==========================================
# CHART AND MAP DESIGN
# ==========================================

def chart_theme(fig, height=420):
    fig.update_layout(
        height=height,
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(color=WHITE, size=12),
        margin=dict(l=12, r=12, t=30, b=15),
        legend=dict(
            font=dict(color=WHITE),
            bgcolor="rgba(9,25,37,.95)"
        ),
        hoverlabel=dict(
            bgcolor="#17394C",
            font=dict(color=WHITE)
        )
    )
    return fig


def risk_map(nodes):
    fig = go.Figure()
    by_id = {n["id"]: n for n in nodes}

    for n in nodes:
        if n["parent"]:
            p = by_id[n["parent"]]

            fig.add_trace(
                go.Scattermap(
                    lat=[p["lat"], n["lat"]],
                    lon=[p["lon"], n["lon"]],
                    mode="lines",
                    line=dict(
                        width=2,
                        color="#79C3D7"
                    ),
                    showlegend=False,
                    hoverinfo="skip"
                )
            )

    for band in ("Critical", "Elevated", "Low"):
        subset = [
            n for n in nodes
            if n["band"] == band
        ]

        if subset:
            fig.add_trace(
                go.Scattermap(
                    lat=[n["lat"] for n in subset],
                    lon=[n["lon"] for n in subset],
                    mode="markers",
                    name=band,
                    marker=dict(
                        size=15,
                        color=COLORS[band]
                    ),
                    text=[
                        f"{n['name']} | "
                        f"{n['status']} | "
                        f"Risk {n['risk']}"
                        for n in subset
                    ],
                    hovertemplate="%{text}<extra></extra>"
                )
            )

    fig.update_layout(
        map=dict(
            style="carto-darkmatter",
            center=dict(
                lat=25.81,
                lon=-80.27
            ),
            zoom=9.2
        )
    )

    return chart_theme(fig, 480)


def twin_chart(nodes):
    fig = go.Figure()
    by_id = {n["id"]: n for n in nodes}

    for n in nodes:
        if n["parent"]:
            p = by_id[n["parent"]]

            fig.add_trace(
                go.Scatter(
                    x=[p["x"], n["x"]],
                    y=[p["y"], n["y"]],
                    mode="lines",
                    line=dict(
                        color=RED if n["offline"] else CYAN,
                        width=3
                    ),
                    hoverinfo="skip",
                    showlegend=False
                )
            )

    for state, color in (
        ("Direct failure", RED),
        ("Upstream outage", AMBER),
        ("Energized", GREEN)
    ):
        group = [
            n for n in nodes
            if n["status"] == state
        ]

        if group:
            fig.add_trace(
                go.Scatter(
                    x=[n["x"] for n in group],
                    y=[n["y"] for n in group],
                    mode="markers+text",
                    name=state,
                    text=[n["id"] for n in group],
                    textposition="top center",
                    textfont=dict(
                        color=WHITE,
                        size=12
                    ),
                    marker=dict(
                        size=25,
                        color=color,
                        line=dict(
                            color=NAVY,
                            width=2
                        )
                    ),
                    customdata=[
                        n["name"] for n in group
                    ],
                    hovertemplate=(
                        "%{customdata}<extra></extra>"
                    )
                )
            )

    fig.update_xaxes(
        visible=False,
        range=[.4, 3.6]
    )

    fig.update_yaxes(
        visible=False,
        range=[.3, 8.0]
    )

    return chart_theme(fig, 460)


# ==========================================
# EXPLAINABLE RECOMMENDATIONS
# ==========================================

def explain(n):
    return (
        f"Risk {n['risk']}/100; "
        f"serves {n['customers']:,} simulated customers; "
        f"criticality {n['critical']}/100; "
        f"estimated repair {n['estimated_hours']} h. "
        f"Status: {n['status']}. "
        f"Priority {n['priority']}/100. "
        "Human engineering review is required "
        "before any real dispatch."
    )


def briefing(nodes):
    offline = [
        n for n in nodes
        if n["offline"] and n["customers"] > 0
    ]

    ranked = sorted(
        nodes,
        key=lambda n: n["priority"],
        reverse=True
    )

    top = ranked[0]

    return (
        "ILLUSTRATIVE INCIDENT BRIEFING\n\n"
        f"{len(offline)} customer-serving assets show "
        "simulated outages; "
        f"{sum(n['customers'] for n in offline):,} "
        "customer groups are potentially affected.\n\n"
        f"Highest-ranked asset: {top['name']} "
        f"({top['priority']}/100). "
        f"{explain(top)}\n\n"
        "Next steps: verify field conditions, "
        "check crew access and critical facilities, "
        "review upstream dependencies, and obtain "
        "human approval before dispatch."
    )


# ==========================================
# SIDEBAR CONTROLS
# ==========================================

with st.sidebar:
    st.markdown("### 🐞 GridHive")
    st.caption("HACKSTEM · SYNTHETIC DEMONSTRATION")

    category = st.slider(
        "Hurricane category",
        1, 5, 3,
        key="category"
    )

    track = st.selectbox(
        "Scenario landfall",
        list(TRACKS),
        key="track"
    )

    faults = st.toggle(
        "Simulate grid failures",
        value=True,
        key="faults"
    )

    if st.button(
        "Reset demo and inspections",
        use_container_width=True
    ):
        reset_inspections()

        for key in ("category", "track", "faults"):
            st.session_state.pop(key, None)

        st.rerun()

    st.markdown("---")
    st.caption(
        "No live power-grid data or robot control. "
        "Results are illustrative, not forecasts."
    )


records = inspections()
nodes = model(category, track, faults, records)

ranked = sorted(
    nodes,
    key=lambda n: n["priority"],
    reverse=True
)

offline = [
    n for n in nodes
    if n["offline"] and n["customers"] > 0
]

affected = sum(
    n["customers"] for n in offline
)

# ==========================================
# COMMAND CENTER HEADER
# ==========================================

st.markdown("""
<div class='hero'>
    <div class='eyebrow'>
        GRIDHIVE / OPERATIONS INTELLIGENCE
    </div>
    <h1>the Anthill</h1>
    <p>
        Hurricane resilience command center ·
        inspection intelligence ·
        restoration planning
    </p>
</div>
""", unsafe_allow_html=True)

st.info(
    "Prototype mode: all asset locations, "
    "failures, risk scores and economic "
    "estimates are simulated."
)

m1, m2, m3, m4 = st.columns(4)

m1.metric("Monitored assets", len(nodes))
m2.metric(
    "Critical-risk assets",
    sum(n["band"] == "Critical" for n in nodes)
)
m3.metric(
    "Affected service customers",
    f"{affected:,}"
)
m4.metric(
    "Inspections submitted",
    len(records)
)

# ==========================================
# SIX DASHBOARD SECTIONS
# ==========================================

(
    overview,
    storm_tab,
    inspect_tab,
    restore_tab,
    twin_tab,
    impact_tab
) = st.tabs([
    "Overview",
    "Hurricane simulator",
    "Robot inspections",
    "Restoration AI",
    "Grid digital twin",
    "Community impact"
])

# 1. OVERVIEW

with overview:
    left, right = st.columns([1.65, 1])

    with left:
        st.subheader("Florida asset risk map")
        st.plotly_chart(
            risk_map(nodes),
            use_container_width=True
        )

    with right:
        st.subheader("Restoration priority queue")

        queue = pd.DataFrame([
            {
                "Asset": n["name"],
                "Risk": n["risk"],
                "Priority": n["priority"],
                "State": n["status"]
            }
            for n in ranked
        ])

        st.dataframe(
            queue,
            use_container_width=True,
            hide_index=True,
            height=465
        )

    st.subheader("Risk by infrastructure asset")

    fig = go.Figure(
        go.Bar(
            x=[n["name"] for n in ranked],
            y=[n["risk"] for n in ranked],
            marker_color=[
                COLORS[n["band"]] for n in ranked
            ]
        )
    )

    fig.update_yaxes(
        range=[0, 100],
        gridcolor="#31566A",
        title="Risk score / 100"
    )
    fig.update_xaxes(tickangle=-30)

    st.plotly_chart(
        chart_theme(fig, 340),
        use_container_width=True
    )

# 2. HURRICANE SIMULATOR

with storm_tab:
    st.subheader("Hurricane scenario engine")

    st.write(
        f"Current demonstration: **Category {category}**, "
        f"approximate landfall **{track}**."
    )

    st.markdown(
        "<div class='note'>Move the hurricane controls "
        "in the sidebar to recalculate exposure, "
        "synthetic failures and the repair queue.</div>",
        unsafe_allow_html=True
    )

    trends = []

    for cat in range(1, 6):
        scenario = model(
            cat, track, faults, records
        )

        trends.append({
            "Category": f"Cat {cat}",
            "Critical assets": sum(
                n["band"] == "Critical"
                for n in scenario
            ),
            "Affected customers": sum(
                n["customers"]
                for n in scenario
                if n["offline"]
            )
        })

    a, b = st.columns(2)

    with a:
        st.subheader("Simulated critical assets")
        st.bar_chart(
            pd.DataFrame(trends)
            .set_index("Category")["Critical assets"],
            color=CYAN
        )

    with b:
        st.subheader("Simulated affected customers")
        st.bar_chart(
            pd.DataFrame(trends)
            .set_index("Category")["Affected customers"],
            color=AMBER
        )

    st.caption(
        "Simplified distance-and-exposure scoring model. "
        "Not a meteorological or utility reliability forecast."
    )

# 3. ROBOT INSPECTIONS

with inspect_tab:
    st.subheader(
        "TerraBeetle / AeroTerra inspection intake"
    )

    st.write(
        "Upload a photo from a camera or phone, "
        "record the observed condition, "
        "and update the priority queue."
    )

    with st.form(
        "inspection_form",
        clear_on_submit=True
    ):
        selected = st.selectbox(
            "Infrastructure asset",
            [n["name"] for n in nodes]
        )

        damage = st.slider(
            "Confirmed damage severity (manual assessment)",
            0, 100, 65
        )

        notes = st.text_area(
            "Inspection notes",
            placeholder=(
                "Describe what was observed. "
                "Do not enter sensitive utility information."
            )
        )

        photo = st.file_uploader(
            "Optional inspection image (JPEG/PNG, 5 MB max)",
            type=["jpg", "jpeg", "png"]
        )

        submit = st.form_submit_button(
            "Save inspection and update risk",
            type="primary"
        )

    if submit:
        try:
            aid = next(
                n["id"] for n in nodes
                if n["name"] == selected
            )

            save_inspection(
                aid,
                damage,
                notes[:1200],
                process_photo(photo)
            )

            st.success(
                "Inspection saved. Risk map and repair "
                "priorities have been updated."
            )

            st.rerun()

        except ValueError as exc:
            st.error(str(exc))

    if records:
        st.subheader("Recent inspection reports")

        lookup = {
            n["id"]: n["name"]
            for n in nodes
        }

        for ident, aid, sev, note, img, created in records[:8]:
            with st.expander(
                f"{created} · "
                f"{lookup.get(aid, aid)} · "
                f"severity {sev}"
            ):
                st.write(
                    note or "No notes provided"
                )

                if img:
                    st.image(img, width=360)
    else:
        st.caption(
            "No inspections yet. Submit one to "
            "demonstrate a dashboard update."
        )

# 4. RESTORATION AI / DECISION SUPPORT

with restore_tab:
    st.subheader(
        "Explainable restoration recommendations"
    )

    st.caption(
        "Priority = 38% risk + 25% customers "
        "+ 27% criticality + 10% repair speed. "
        "Direct failures receive a bonus."
    )

    asset = st.selectbox(
        "Inspect priority reasoning",
        [n["name"] for n in ranked]
    )

    chosen = next(
        n for n in ranked
        if n["name"] == asset
    )

    st.metric(
        "Priority score",
        f"{chosen['priority']}/100"
    )

    st.markdown(
        f"<div class='note'>{explain(chosen)}</div>",
        unsafe_allow_html=True
    )

    st.subheader("Incident briefing")

    if st.button(
        "Generate incident briefing",
        type="primary"
    ):
        st.session_state["briefing"] = briefing(nodes)

    st.text_area(
        "Decision-support report",
        value=st.session_state.get(
            "briefing",
            briefing(nodes)
        ),
        height=215
    )

    st.caption(
        "The default briefing is rule-based, "
        "not an autonomous repair instruction."
    )

    key = os.getenv("GEMINI_API_KEY", "")

    if key:
        if st.button(
            "Ask Gemini to summarize this scenario"
        ):
            try:
                from google import genai

                client = genai.Client(
                    api_key=key
                )

                prompt = (
                    "Summarize this synthetic hurricane-grid "
                    "demonstration for judges in 150 words. "
                    "Do not assert live measurements or give "
                    "operational switching commands.\n"
                    + briefing(nodes)
                )

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )

                st.session_state["gemini_briefing"] = (
                    response.text or "No response"
                )

            except Exception as exc:
                st.warning(
                    "AI service unavailable: "
                    f"{type(exc).__name__}. "
                    "The rule-based briefing still works."
                )

        if st.session_state.get("gemini_briefing"):
            st.write(
                st.session_state["gemini_briefing"]
            )

# 5. GRID DIGITAL TWIN

with twin_tab:
    st.subheader(
        "Synthetic electrical network digital twin"
    )

    st.plotly_chart(
        twin_chart(nodes),
        use_container_width=True
    )

    st.caption(
        "Red = directly failed; amber = disconnected "
        "by upstream failure; green = energized. "
        "This is a dependency graph, not a power-flow model."
    )

    st.dataframe(
        pd.DataFrame([
            {
                "ID": n["id"],
                "Asset": n["name"],
                "Upstream": n["parent"] or "—",
                "Status": n["status"]
            }
            for n in nodes
        ]),
        use_container_width=True,
        hide_index=True
    )

# 6. COMMUNITY + ECONOMIC IMPACT

with impact_tab:
    st.subheader(
        "Community and economic impact scenarios"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        cost = st.number_input(
            "Illustrative outage cost per customer-hour ($)",
            1.0, 100.0, 12.0, 1.0
        )

    with c2:
        backup_kw = st.number_input(
            "Backup generator kW per customer (assumption)",
            0.0, 5.0, 0.5, 0.1
        )

    with c3:
        emissions = st.number_input(
            "Generator kg CO₂ per kWh (assumption)",
            0.0, 2.0, 0.7, 0.1
        )

    customer_hours = sum(
        n["customers"] * n["estimated_hours"]
        for n in offline
    )

    p1, p2, p3 = st.columns(3)

    p1.metric(
        "Estimated customer-outage hours",
        f"{customer_hours:,.0f}"
    )

    p2.metric(
        "Illustrative economic exposure",
        f"${customer_hours * cost:,.0f}"
    )

    p3.metric(
        "Backup generation CO₂ scenario",
        f"{customer_hours * backup_kw * emissions:,.0f} kg"
    )

    st.caption(
        "Assumption-based calculations, not measured "
        "outage costs, emissions, or validated benefits."
    )

    if offline:
        impacts = pd.DataFrame([
            {
                "Asset": n["name"],
                "Customer-outage hours": round(
                    n["customers"] * n["estimated_hours"]
                )
            }
            for n in offline
        ])

        st.bar_chart(
            impacts.set_index("Asset"),
            color=CYAN
        )
    else:
        st.success(
            "No simulated customer outages "
            "in the current scenario."
        )

st.divider()

st.caption(
    "GridHive HackSTEM semifinal prototype · "
    "Synthetic infrastructure and financial data · "
    "Human review required"
)