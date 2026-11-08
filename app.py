"""the Anthill V4 - GridHive educational prototype."""

import hashlib
import html
import os
from io import BytesIO

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from folium.plugins import Fullscreen
from PIL import Image, ImageOps, UnidentifiedImageError
from streamlit_folium import st_folium

import storage

from gridhive_core import (
    ASSETS,
    TRACKS,
    scenario,
    outage_states,
    affected_customers,
    repair_plan,
    verified_max,
    summary
)

st.set_page_config(
    page_title="the Anthill | GridHive",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Restrained engineering operations design.
# No gradients, glowing panels, or stock images.

st.markdown("""
<style>
:root {
    color-scheme: dark;
}

.stApp,
[data-testid="stAppViewContainer"] {
    background: #0D1822;
    color: #F1F5F7;
}

[data-testid="stSidebar"] {
    background: #101F2B;
    border-right: 1px solid #344B5A;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stMetric"] {
    background: #142633;
    border: 1px solid #385063;
    border-radius: 4px;
    padding: 13px 16px;
}

[data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"] * {
    color: #F1F5F7 !important;
}

[data-testid="stCaptionContainer"] *,
.stCaption {
    color: #C4D3DE !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    line-height: 1.5;
}

.stApp h1,
.stApp h2,
.stApp h3 {
    color: #F1F5F7;
    letter-spacing: -.02em;
}

.stApp h1 {
    font-size: 1.8rem;
}

.stApp h2 {
    font-size: 1.35rem;
}

.stApp h3 {
    font-size: 1.1rem;
}

[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
textarea,
input {
    background-color: #193141 !important;
    color: #F5FAFD !important;
    border-color: #648296 !important;
}

[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"] {
    background: #193141 !important;
    color: #F5FAFD !important;
}

[data-baseweb="popover"] [role="option"]:hover {
    background: #315367 !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #385063;
}

.stButton button {
    border-radius: 4px;
    font-weight: 600;
}

.stButton button[kind="primary"] {
    background: #147B89;
    color: #FFFFFF;
    border: 1px solid #72D7D5;
}

.stButton button[kind="secondary"] {
    background: #203A4C;
    color: #FFFFFF;
    border: 1px solid #7895A5;
}

.stButton button:focus-visible {
    outline: 3px solid #8FE2E0;
}

.app-kicker {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: .13em;
    color: #83D5D5;
}

.app-heading {
    border-bottom: 1px solid #344B5A;
    padding-bottom: 13px;
    margin-bottom: 20px;
}

.app-heading h1 {
    margin: 3px 0 4px;
    font-weight: 650;
}

.app-subtitle {
    color: #D0DCE4;
    font-size: 14px;
}

.status-strip {
    border: 1px solid #476071;
    background: #172B39;
    padding: 10px 13px;
    border-radius: 4px;
    color: #E6F2F6;
    font-size: 13px;
    margin-bottom: 17px;
}
</style>
""", unsafe_allow_html=True)

try:
    storage.init()
except Exception:
    st.error(
        "Database unavailable. Check DATABASE_URL "
        "or local SQLite file permissions."
    )
    st.stop()

if "mission_step" not in st.session_state:
    st.session_state.mission_step = 0

if "selected_asset" not in st.session_state:
    st.session_state.selected_asset = "M-F"

if "manual_failures" not in st.session_state:
    st.session_state.manual_failures = []

# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------

with st.sidebar:
    st.markdown("**GRIDHIVE**")
    st.caption("HACKSTEM / THE ANTHILL V4")

    page = st.radio(
        "WORKSPACE",
        [
            "Overview",
            "Mission Control",
            "Inspections",
            "Restoration",
            "Digital Twin",
            "Impact",
            "Activity"
        ]
    )

    st.divider()
    st.markdown("**SCENARIO CONTROLS**")

    sidebar_category = st.slider(
        "Storm category", 1, 5, 4
    )

    sidebar_track = st.selectbox(
        "Landfall area",
        list(TRACKS)
    )

    category = st.session_state.get(
        "mission_category", sidebar_category
    )

    track = st.session_state.get(
        "mission_track", sidebar_track
    )

    if "mission_category" in st.session_state:
        st.caption(
            "Mission Control is overriding "
            "the scenario controls."
        )

    if st.button(
        "Use sidebar scenario",
        use_container_width=True
    ):
        st.session_state.pop(
            "mission_category", None
        )
        st.session_state.pop(
            "mission_track", None
        )

        storage.log(
            "SCENARIO",
            "Returned to manual scenario controls"
        )
        st.rerun()

    st.divider()

    st.caption(
        "Synthetic grid assets. No operational "
        "switching, live outage data, or "
        "autonomous dispatch."
    )

    if storage.DB_URL:
        st.caption("Storage: PostgreSQL configured.")
    else:
        st.caption(
            "Storage: local SQLite. "
            "Cloud restarts may erase records."
        )

# --------------------------------------------------
# COMPUTE SHARED SYSTEM STATE
# --------------------------------------------------

records = storage.list_inspections()

nodes = scenario(
    category,
    track,
    verified_max(records),
    st.session_state.manual_failures
)

states = outage_states(nodes)

by_id = {
    n["id"]: n for n in nodes
}

strategies = (
    "Balanced",
    "Customers first",
    "Fastest restoration",
    "Critical facilities"
)

plans = {
    name: repair_plan(nodes, name)
    for name in strategies
}

base_plan = plans["Balanced"]

affected = affected_customers(nodes)

failed_count = sum(
    n["direct_failed"] for n in nodes
)

st.markdown("""
<div class="app-heading">
    <div class="app-kicker">
        GRIDHIVE / RESILIENCE OPERATIONS
    </div>
    <h1>the Anthill</h1>
    <div class="app-subtitle">
        Infrastructure monitoring, inspection review,
        and restoration decision support
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="status-strip">'
    'DEMONSTRATION MODE &nbsp;·&nbsp; '
    f'Category {category} &nbsp;·&nbsp; '
    f'{html.escape(track)} &nbsp;·&nbsp; '
    'All grid data and storm effects are simulated'
    '</div>',
    unsafe_allow_html=True
)

k1, k2, k3, k4 = st.columns(4)

k1.metric("Grid assets", len(nodes))
k2.metric("Direct failures", failed_count)
k3.metric(
    "Unique customers affected",
    f"{affected:,}"
)
k4.metric(
    "Pending inspections",
    sum(not r["verified"] for r in records)
)

# --------------------------------------------------
# REUSABLE COMPONENTS
# --------------------------------------------------

def asset_map(height=510):
    m = folium.Map(
        location=[28.05, -81.55],
        zoom_start=6.45,
        tiles="CartoDB dark_matter",
        control_scale=True,
        prefer_canvas=True
    )

    Fullscreen(position="topright").add_to(m)

    for n in nodes:
        if n["parent"]:
            parent = by_id[n["parent"]]

            folium.PolyLine(
                [
                    [parent["lat"], parent["lon"]],
                    [n["lat"], n["lon"]]
                ],
                color="#7BA7B8",
                weight=2,
                opacity=.7
            ).add_to(m)

    for n in nodes:
        state = states[n["id"]]["status"]

        color = (
            "#EE6673" if state == "Failed"
            else "#F1BD69"
            if state == "Upstream outage"
            else "#57C6AD"
        )

        label = (
            f"{n['name']} | "
            f"Risk {n['risk']}/100 | {state}"
        )

        folium.CircleMarker(
            [n["lat"], n["lon"]],
            radius=9 if n["kind"] == "Substation" else 7,
            color="#E8F1F4",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=.95,
            tooltip=label,
            popup=folium.Popup(
                html.escape(label),
                max_width=300
            )
        ).add_to(m)

    result = st_folium(
        m,
        height=height,
        use_container_width=True,
        key=f"map_{page}",
        returned_objects=["last_object_clicked"]
    )

    click = (
        result.get("last_object_clicked")
        if result else None
    )

    if click:
        nearest = min(
            nodes,
            key=lambda n: (
                (n["lat"] - click["lat"]) ** 2
                + (n["lon"] - click["lng"]) ** 2
            )
        )

        if (
            abs(nearest["lat"] - click["lat"]) < .015
            and abs(nearest["lon"] - click["lng"]) < .015
        ):
            st.session_state.selected_asset = nearest["id"]


def asset_detail(asset_id):
    n = by_id[asset_id]

    st.markdown(f"**{n['name']}**")

    st.caption(
        f"{n['region']} · {n['kind']} · {n['id']}"
    )

    a, b = st.columns(2)

    a.metric("Risk / 100", n["risk"])
    b.metric(
        "Status",
        states[asset_id]["status"]
    )

    st.write(
        f"Criticality: **{n['critical']}/100** · "
        "Unique service customers: "
        f"**{n['customers']:,}**"
    )

    st.caption(
        "Asset names and locations are "
        "fictionalized demonstration examples."
    )


def event_table():
    events = storage.events()

    if events:
        df = pd.DataFrame(events)

        df = df[
            ["created_at", "category", "message"]
        ].rename(columns={
            "created_at": "UTC time",
            "category": "Event",
            "message": "Details"
        })

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info(
            "No events yet. Run Mission Control "
            "or submit an inspection."
        )


# ==================================================
# OVERVIEW
# ==================================================

if page == "Overview":
    left, right = st.columns(
        [1.8, 1],
        gap="large"
    )

    with left:
        st.subheader(
            "Florida infrastructure overview"
        )

        asset_map()

        st.caption(
            "Click a marker to inspect its "
            "modeled condition. Markers show "
            "failed, upstream-outage, or "
            "energized status."
        )

    with right:
        st.subheader("Selected asset")

        st.session_state["selected_asset_widget"] = (
            st.session_state.selected_asset
        )

        selected = st.selectbox(
            "Asset",
            [n["id"] for n in nodes],
            key="selected_asset_widget",
            format_func=lambda x: by_id[x]["name"]
        )

        st.session_state.selected_asset = selected

        asset_detail(selected)

        st.divider()
        st.subheader("Next recommended repair")

        if base_plan["schedule"]:
            top = base_plan["schedule"][0]

            st.write(f"**{top['asset']}**")

            st.metric(
                "Customers restored by this repair",
                f"{top['restored']:,}"
            )

            st.caption(
                "Single-crew sequential repair "
                "assumption. Confirm field conditions."
            )
        else:
            st.success(
                "No direct failures in this simulation."
            )

        st.subheader("Latest activity")

        for event in storage.events()[:3]:
            st.caption(
                f"{event['created_at']} · "
                f"{event['category']}"
            )
            st.write(event["message"])

    st.subheader("Risk register")

    df = pd.DataFrame([
        {
            "Asset": n["name"],
            "Region": n["region"],
            "Risk": n["risk"],
            "Status": states[n["id"]]["status"],
            "Customers served": n["customers"]
        }
        for n in nodes
    ]).sort_values(
        "Risk", ascending=False
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

# ==================================================
# MISSION CONTROL
# ==================================================

elif page == "Mission Control":
    st.subheader("Guided hurricane response")

    st.write(
        "A repeatable six-stage demonstration. "
        "Each action updates the same scenario, "
        "inspection records, and restoration model."
    )

    labels = [
        "Ready",
        "Storm launched",
        "Risk assessed",
        "Inspection received",
        "Inspection approved",
        "Restoration planned",
        "Impact brief ready"
    ]

    step = st.session_state.mission_step

    st.progress(
        step / 6,
        text=f"Stage {step}/6 · {labels[step]}"
    )

    st.markdown(f"### {labels[step]}")

    if step == 0:
        st.write(
            "Begin a Category 4 Miami coastal scenario."
        )

        if st.button(
            "Launch hurricane simulation",
            type="primary"
        ):
            st.session_state.mission_category = 4
            st.session_state.mission_track = "Miami coast"
            st.session_state.mission_step = 1

            storage.log(
                "STORM",
                "Category 4 Miami coastal "
                "simulation launched"
            )
            st.rerun()

    elif step == 1:
        st.write(
            f"The scenario affects **{affected:,}** "
            "unique modeled customers."
        )

        if st.button(
            "Assess infrastructure risk",
            type="primary"
        ):
            st.session_state.mission_step = 2

            storage.log(
                "RISK",
                f"Exposure assessed: "
                f"{failed_count} direct failures"
            )
            st.rerun()

    elif step == 2:
        st.write(
            "Create a clearly simulated TerraBeetle "
            "inspection. No live robot or camera "
            "is implied."
        )

        if st.button(
            "Receive simulated TerraBeetle inspection",
            type="primary"
        ):
            storage.add_inspection(
                "M-A",
                94,
                "Simulated TerraBeetle",
                "Synthetic demonstration: visible "
                "infrastructure damage requiring review."
            )

            st.session_state.mission_inspection = (
                storage.list_inspections()[0]["id"]
            )

            st.session_state.mission_step = 3
            st.rerun()

    elif step == 3:
        st.warning(
            "Inspection is pending human verification "
            "and has not changed modeled risk."
        )

        if st.button(
            "Approve demo inspection as reviewer",
            type="primary"
        ):
            storage.approve(
                st.session_state.mission_inspection
            )

            st.session_state.mission_step = 4
            st.rerun()

    elif step == 4:
        st.write(
            "Approved severity now influences "
            "the risk model."
        )

        if st.button(
            "Calculate restoration plan",
            type="primary"
        ):
            storage.log(
                "RESTORATION",
                "Human-review restoration "
                "options calculated"
            )

            st.session_state.mission_step = 5
            st.rerun()

    elif step == 5:
        st.write(summary(nodes, base_plan))

        if st.button(
            "Generate community impact brief",
            type="primary"
        ):
            storage.log(
                "IMPACT",
                "Illustrative baseline: "
                f"{base_plan['customer_hours']:,} "
                "customer-outage hours"
            )

            st.session_state.mission_step = 6
            st.rerun()

    else:
        st.success(
            "Full workflow completed. "
            "Use Overview, Restoration, and Impact "
            "to show the linked results."
        )

        st.code(
            summary(nodes, base_plan),
            language=None
        )

    st.divider()

    if st.button(
        "Reset shared demo data and mission",
        help="Deletes all demo inspection "
             "and activity records."
    ):
        storage.reset()

        for key in (
            "mission_category",
            "mission_track",
            "mission_inspection",
            "ai_note",
            "image_sig"
        ):
            st.session_state.pop(key, None)

        st.session_state.mission_step = 0
        st.session_state.manual_failures = []
        st.rerun()

    st.subheader("Current scenario")

    a, b, c = st.columns(3)

    a.metric("Storm", f"Category {category}")
    b.metric("Modeled failures", failed_count)
    c.metric(
        "Affected customers",
        f"{affected:,}"
    )

# ==================================================
# INSPECTIONS + CAMERA + OPTIONAL GEMINI
# ==================================================

elif page == "Inspections":
    st.subheader(
        "Inspection intake and review"
    )

    st.write(
        "Use your browser camera or upload an image. "
        "AI observations are optional and never "
        "automatically verified."
    )

    left, right = st.columns(
        [1, 1],
        gap="large"
    )

    with left:
        asset_id = st.selectbox(
            "Inspected asset",
            [n["id"] for n in nodes],
            format_func=lambda x: by_id[x]["name"]
        )

        camera = st.camera_input(
            "Capture using browser camera"
        )

        upload = st.file_uploader(
            "Or upload JPEG/PNG (5 MB maximum)",
            type=["jpg", "jpeg", "png"]
        )

        chosen_file = camera or upload

        source = (
            "Browser camera" if camera
            else "Uploaded image" if upload
            else "Manual observation"
        )

        severity = st.slider(
            "Observed damage severity / 100 "
            "(human estimate)",
            0, 100, 65
        )

        notes = st.text_area(
            "Field notes",
            placeholder=(
                "Describe visible damage and uncertainty. "
                "Do not enter confidential utility data."
            )
        )

        image_bytes = None

        if chosen_file is not None:
            raw = chosen_file.getvalue()

            if len(raw) > 5_000_000:
                st.error(
                    "Image exceeds 5 MB."
                )
            else:
                try:
                    with Image.open(BytesIO(raw)) as im:
                        if (
                            im.format not in ("JPEG", "PNG")
                            or im.width * im.height
                            > 12_000_000
                        ):
                            raise ValueError(
                                "Only JPEG/PNG images up "
                                "to 12 megapixels supported."
                            )

                        clean = ImageOps.exif_transpose(im)
                        clean.thumbnail((1000, 1000))

                        buffer = BytesIO()

                        clean.convert("RGB").save(
                            buffer,
                            "JPEG",
                            quality=82
                        )

                        image_bytes = buffer.getvalue()

                    st.image(
                        image_bytes,
                        caption="Prepared inspection image",
                        width=320
                    )

                except (
                    ValueError,
                    UnidentifiedImageError,
                    OSError,
                    Image.DecompressionBombError
                ) as exc:
                    st.error(
                        f"Invalid image: {exc}"
                    )

        fingerprint = (
            hashlib.sha256(image_bytes).hexdigest()
            if image_bytes else "none"
        )

        if (
            st.session_state.get("image_sig")
            != fingerprint
        ):
            st.session_state.image_sig = fingerprint
            st.session_state.ai_note = ""

        try:
            key = (
                os.getenv("GEMINI_API_KEY")
                or st.secrets.get("GEMINI_API_KEY", "")
            )
        except Exception:
            key = os.getenv("GEMINI_API_KEY", "")

        if st.button(
            "Analyze image with Gemini (optional)",
            disabled=not (image_bytes and key)
        ):
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=key)

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        "This is an electric-grid inspection "
                        "training image. Describe only visible "
                        "features, possible concerns, and "
                        "uncertainties in under 120 words. "
                        "Do not claim confirmed damage or "
                        "prescribe electrical switching.",
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/jpeg"
                        )
                    ]
                )

                st.session_state.ai_note = (
                    response.text
                    or "No observation returned"
                )[:1500]

            except Exception:
                st.error(
                    "Image analysis unavailable. "
                    "Manual inspection still works."
                )

        if not key:
            st.caption(
                "Set GEMINI_API_KEY as a server secret "
                "to enable optional AI observations."
            )

        if st.session_state.get("ai_note"):
            st.info(
                "Unverified AI observation: "
                + st.session_state.ai_note
            )

        if st.button(
            "Submit for human verification",
            type="primary"
        ):
            storage.add_inspection(
                asset_id,
                severity,
                source,
                notes,
                image_bytes,
                st.session_state.get("ai_note", "")
            )

            st.session_state.ai_note = ""

            st.success(
                "Inspection saved as PENDING. "
                "It will not change modeled risk "
                "until approved."
            )
            st.rerun()

    with right:
        st.subheader("Review queue")

        if not records:
            st.info("No inspection records yet.")

        for rec in records[:15]:
            status = (
                "VERIFIED" if rec["verified"]
                else "PENDING"
            )

            name = by_id.get(
                rec["asset_id"], {}
            ).get(
                "name", rec["asset_id"]
            )

            with st.expander(
                f"#{rec['id']} · {name} · {status}"
            ):
                st.caption(
                    f"{rec['created_at']} · "
                    f"{rec['source']} · "
                    f"severity {rec['severity']}/100"
                )

                st.write(
                    rec["notes"] or "No notes"
                )

                if rec["ai_note"]:
                    st.write(
                        "**AI observation (unverified):** "
                        + rec["ai_note"]
                    )

                if rec["image"]:
                    st.image(
                        bytes(rec["image"]),
                        width=300
                    )

                if (
                    not rec["verified"]
                    and st.button(
                        "Verify observation",
                        key=f"approve_{rec['id']}"
                    )
                ):
                    storage.approve(rec["id"])
                    st.rerun()

    st.caption(
        "Browser camera uses your device camera, "
        "not a Raspberry Pi CSI or ESP32 camera stream. "
        "Dedicated robot-camera ingestion requires "
        "a separate hardware integration."
    )

# ==================================================
# RESTORATION STRATEGY COMPARISON
# ==================================================

elif page == "Restoration":
    st.subheader(
        "Restoration strategy comparison"
    )

    st.write(
        "Compare four transparent heuristics using "
        "the same simulated faults and one repair "
        "crew working sequentially."
    )

    comparison = pd.DataFrame([
        {
            "Strategy": name,
            "Customer-outage hours": plan[
                "customer_hours"
            ],
            "Total repair hours": plan[
                "total_hours"
            ]
        }
        for name, plan in plans.items()
    ])

    st.dataframe(
        comparison,
        hide_index=True,
        use_container_width=True
    )

    fig = go.Figure(
        go.Bar(
            x=comparison["Strategy"],
            y=comparison["Customer-outage hours"],
            marker_color="#58B9BD"
        )
    )

    fig.update_layout(
        paper_bgcolor="#142633",
        plot_bgcolor="#142633",
        font_color="#E8F1F5",
        margin=dict(l=20, r=10, t=20, b=20),
        height=300
    )

    fig.update_yaxes(
        gridcolor="#3C5363",
        title="Customer-outage hours"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    strategy = st.selectbox(
        "View repair schedule",
        list(plans)
    )

    plan = plans[strategy]

    if plan["schedule"]:
        schedule_df = pd.DataFrame(
            plan["schedule"]
        ).rename(columns={
            "asset": "Repair target",
            "hours": "Duration (h)",
            "restored": "Customers restored",
            "finished_h": "Finish (h)",
            "affected_after": "Customers still out"
        }).drop(columns="id")

        st.dataframe(
            schedule_df,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.success(
            "No direct failures to repair."
        )

    st.info(summary(nodes, plan))

    st.caption(
        "Customer counts exist only at terminal "
        "service zones. An upstream repair only "
        "restores customers when no remaining "
        "downstream failure blocks service."
    )

# ==================================================
# GRID DIGITAL TWIN
# ==================================================

elif page == "Digital Twin":
    st.subheader(
        "Grid dependency model"
    )

    st.write(
        "Explore the parent-child network. "
        "This models outage propagation, "
        "not electrical power flow."
    )

    region = st.selectbox(
        "Network region",
        list(dict.fromkeys(
            n["region"] for n in nodes
        ))
    )

    subset = [
        n for n in nodes
        if n["region"] == region
    ]

    xs = {}
    ys = {}

    for n in subset:
        if n["kind"] == "Substation":
            xs[n["id"]] = 1
            ys[n["id"]] = 3

        elif n["kind"] == "Feeder":
            xs[n["id"]] = 1
            ys[n["id"]] = 2

        else:
            xs[n["id"]] = (
                .35 if n["id"] == "M-A"
                else 1.65 if n["id"] == "M-B"
                else 1
            )
            ys[n["id"]] = 1

    fig = go.Figure()

    for n in subset:
        if n["parent"]:
            fig.add_trace(
                go.Scatter(
                    x=[
                        xs[n["parent"]],
                        xs[n["id"]]
                    ],
                    y=[
                        ys[n["parent"]],
                        ys[n["id"]]
                    ],
                    mode="lines",
                    line=dict(
                        color=(
                            "#E5B56C"
                            if states[n["id"]]["offline"]
                            else "#6C9FA9"
                        ),
                        width=3
                    ),
                    showlegend=False,
                    hoverinfo="skip"
                )
            )

    for n in subset:
        state = states[n["id"]]["status"]

        color = (
            "#EE6673" if state == "Failed"
            else "#F1BD69"
            if state == "Upstream outage"
            else "#57C6AD"
        )

        fig.add_trace(
            go.Scatter(
                x=[xs[n["id"]]],
                y=[ys[n["id"]]],
                mode="markers+text",
                text=[n["id"]],
                textposition="top center",
                textfont=dict(
                    color="#F1F5F7",
                    size=14
                ),
                marker=dict(
                    size=26,
                    color=color,
                    line=dict(
                        width=2,
                        color="#D9E7EC"
                    )
                ),
                name=n["name"],
                hovertemplate=(
                    f"{n['name']}<br>{state}"
                    "<extra></extra>"
                )
            )
        )

    fig.update_layout(
        height=380,
        paper_bgcolor="#142633",
        plot_bgcolor="#142633",
        font_color="#E8F1F5",
        xaxis=dict(
            visible=False,
            range=[-.25, 2.25]
        ),
        yaxis=dict(
            visible=False,
            range=[.4, 3.6]
        ),
        margin=dict(
            l=20, r=20, t=20, b=20
        ),
        showlegend=False
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.dataframe(
        pd.DataFrame([
            {
                "ID": n["id"],
                "Asset": n["name"],
                "Parent": n["parent"] or "—",
                "Status": states[n["id"]]["status"],
                "Customers": n["customers"]
            }
            for n in subset
        ]),
        hide_index=True,
        use_container_width=True
    )

    st.caption(
        "Red: direct failure. "
        "Amber: upstream outage. "
        "Teal: energized. "
        "All connections are fictional."
    )

# ==================================================
# COMMUNITY + ECONOMIC IMPACT
# ==================================================

elif page == "Impact":
    st.subheader(
        "Community and economic exposure"
    )

    st.write(
        "Adjust assumptions to estimate impacts. "
        "These are scenario estimates, "
        "not measured savings."
    )

    c1, c2 = st.columns(2)

    with c1:
        hourly_cost = st.number_input(
            "Illustrative economic impact "
            "($ per customer-hour)",
            min_value=0.0,
            max_value=100.0,
            value=12.0,
            step=1.0
        )

    with c2:
        backup_fraction = st.slider(
            "Share of affected customers "
            "needing backup generation",
            0, 100, 20
        ) / 100

    baseline = base_plan["customer_hours"]

    a, b, c = st.columns(3)

    a.metric(
        "Currently affected customers",
        f"{affected:,}"
    )

    b.metric(
        "Modeled customer-outage hours",
        f"{baseline:,}"
    )

    c.metric(
        "Illustrative economic exposure",
        f"${baseline * hourly_cost:,.0f}"
    )

    st.subheader("Strategy sensitivity")

    impact_df = pd.DataFrame([
        {
            "Strategy": name,
            "Customer-outage hours": plan[
                "customer_hours"
            ],
            "Illustrative cost ($)": round(
                plan["customer_hours"] * hourly_cost
            ),
            "Assumed backup customer-hours": round(
                plan["customer_hours"]
                * backup_fraction
            )
        }
        for name, plan in plans.items()
    ])

    st.dataframe(
        impact_df,
        hide_index=True,
        use_container_width=True
    )

    st.caption(
        "Customer-outage hours use one sequential "
        "crew and fixed example repair durations. "
        "Economic multipliers and backup assumptions "
        "are user-adjustable. "
        "No avoided-cost claim is made."
    )

# ==================================================
# ACTIVITY TIMELINE
# ==================================================

else:
    st.subheader("Operations activity")

    st.write(
        "A timestamped record of actions within "
        "this shared demonstration instance."
    )

    if st.button("Refresh activity"):
        st.rerun()

    event_table()

    st.divider()

    st.caption(
        "For persistent records on Render, "
        "provision PostgreSQL and set DATABASE_URL. "
        "This public prototype has no login or "
        "access controls. Do not upload "
        "confidential grid information."
    )

st.divider()

st.caption(
    "GRIDHIVE / THE ANTHILL V4 · "
    "Educational prototype · "
    "Synthetic assets and scenarios · "
    "Human review required"
)