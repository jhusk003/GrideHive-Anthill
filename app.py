"""the Anthill V2 — GridHive HackSTEM demonstration dashboard.

This application is entirely a fictional/illustrative scenario except for images and
notes a presenter manually uploads. It never controls grid equipment or robots.
"""
from __future__ import annotations
import os
from io import BytesIO
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

from gridhive_core import (
    ASSETS, LINKS, RISK_COLORS, STORMS, TRACKS, simulate, briefing, economic_impact,
)
from inspection_store import (
    add as save_inspection, list_inspections, find_image, reset_demo_inspections,
)

st.set_page_config(page_title='the Anthill | GridHive V2', page_icon='🐞', layout='wide',
                   initial_sidebar_state='expanded')

STYLES = '''
<style>
:root {color-scheme: dark;}
.stApp {background:linear-gradient(145deg,#091524 0%,#0b1a2b 55%,#0b1724 100%);}
[data-testid="stSidebar"] {background:#0c1d2e;}
.block-container {padding-top:1.3rem; padding-bottom:2rem; max-width:1540px;}
h1,h2,h3 {letter-spacing:-0.025em;}
.hero {background:linear-gradient(108deg,#103c45 0%,#16354c 53%,#15213a 100%);
       border:1px solid #245c65;border-radius:18px;padding:25px 30px;margin-bottom:18px;}
.hero-title {font-size:2.3rem;font-weight:850;letter-spacing:-.035em;color:#f1fbfa;line-height:1.1;}
.hero-lead {font-size:1.02rem;color:#c2e3dd;margin-top:7px;}
.hero-cap {font-size:.76rem;text-transform:uppercase;letter-spacing:2.5px;color:#7defcc;font-weight:700;margin-bottom:10px;}
.small-cap {color:#75b9ae;font-size:.75rem;text-transform:uppercase;letter-spacing:1.4px;font-weight:700;}
.info-tile {background:#12293c;border:1px solid #24465a;border-radius:12px;padding:15px 17px;margin:4px 0;}
.info-tile b {color:#eefaf9;font-size:.95rem;}
.info-tile p {color:#b2ccd1;font-size:.85rem;margin-top:3px;margin-bottom:0;}
.note {background:#112538;padding:12px 15px;border-left:3px solid #3cd6b0;border-radius:8px;color:#c0dbdd;}
div[data-testid="stMetric"] {background:#102739;border:1px solid #28475a;border-radius:12px;padding:10px 15px;}
div[data-testid="stMetricLabel"] {color:#9fbdbd;}
.stTabs [data-baseweb="tab-list"]{gap:10px;}
.stTabs [data-baseweb="tab"]{background:#10283b;border-radius:8px 8px 0 0;padding:10px 14px;}
.stTabs [aria-selected="true"]{background:#173b48;}
</style>
'''
st.markdown(STYLES, unsafe_allow_html=True)


def reset_demo():
    reset_demo_inspections()
    for k, v in {'storm': 'Category 3', 'track': 'Miami coast', 'simulate_faults': True}.items():
        st.session_state[k] = v
    st.session_state.pop('ai_briefing', None)
    st.session_state['flash'] = 'Demo reset to default settings; inspection records cleared.'


def flash():
    if st.session_state.get('flash'):
        st.success(st.session_state.pop('flash'))


def get_api_key():
    if os.getenv('GEMINI_API_KEY'):
        return os.environ['GEMINI_API_KEY']
    try:
        return st.secrets.get('GEMINI_API_KEY', '')
    except (FileNotFoundError, KeyError):
        return ''


def ask_gemini(prompt, image_bytes=None):
    from google import genai
    client = genai.Client(api_key=get_api_key())
    model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    contents = [prompt]
    if image_bytes:
        photo = Image.open(BytesIO(image_bytes))
        contents.append(photo)
    response = client.models.generate_content(model=model, contents=contents)
    return (response.text or '').strip() or 'No response returned. Please use the transparent rule-based summary.'


def optimized_photo(file):
    if file is None:
        return None
    payload = file.getvalue()
    if len(payload) > 5 * 1024 * 1024:
        raise ValueError('Maximum image size is 5 MB.')
    try:
        with Image.open(BytesIO(payload)) as original:
            if original.format not in ('JPEG', 'PNG'):
                raise ValueError('Please use a JPEG or PNG image.')
            if original.width * original.height > 12_000_000:
                raise ValueError('Image exceeds the 12-megapixel demo limit.')
            # Re-encode to a clean JPEG; strip camera metadata and reduce DB storage.
            img = ImageOps.exif_transpose(original)
            img.thumbnail((1300, 1300))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            result = BytesIO()
            img.save(result, format='JPEG', quality=85)
            return result.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Unable to read this image safely.') from exc


def map_chart(result):
    nodes = result['nodes']
    fig = go.Figure()
    by_id = {n['id']: n for n in nodes}
    for upstream, downstream in LINKS:
        u, v = by_id[upstream], by_id[downstream]
        fig.add_trace(go.Scattermap(
            lat=[u['lat'], v['lat']], lon=[u['lon'], v['lon']], mode='lines',
            line=dict(width=1.7,color='#627f8b'), opacity=0.5,
            hoverinfo='skip', showlegend=False,
        ))
    for band in ['Critical', 'Elevated', 'Low']:
        group = [n for n in nodes if n['risk'] == band]
        if not group:
            continue
        fig.add_trace(go.Scattermap(
            lat=[n['lat'] for n in group], lon=[n['lon'] for n in group],
            mode='markers',name=band,
            marker=dict(size=[12 + min(21, n['customers']/160) for n in group],
                        color=RISK_COLORS[band],opacity=.92),
            text=[n['name'] for n in group],
            customdata=[[n['severity'],n['state'],n['customers']] for n in group],
            hovertemplate='<b>%{text}</b><br>Risk score: %{customdata[0]:.1f}/100'
                          '<br>Status: %{customdata[1]}<br>Customers served: %{customdata[2]:,}<extra></extra>',
        ))
    fig.update_layout(
        map=dict(style='open-street-map',center=dict(lat=25.75,lon=-80.32),zoom=7.3),
        height=470, margin=dict(t=12,b=0,l=0,r=0),
        paper_bgcolor='#10283b', plot_bgcolor='#10283b',
        font=dict(color='#cfebed'),
        legend=dict(orientation='h',yanchor='bottom',y=0.97,xanchor='left',x=0.02,bgcolor='rgba(9,21,36,.82)'),
    )
    return fig


def grid_graph(result):
    by_id = {n['id']: n for n in result['nodes']}
    fig = go.Figure()
    for up_id, down_id in LINKS:
        u, v = by_id[up_id], by_id[down_id]
        col = '#e56578' if v['offline'] else '#2d9d91'
        fig.add_trace(go.Scatter(
            x=[u['x'],v['x']], y=[u['y'],v['y']], mode='lines',
            line=dict(color=col,width=3), hoverinfo='skip', showlegend=False,
        ))
    for state, fill, name in [
        ('failed','#ff7189','Direct failure'),
        ('outage','#e6a352','Upstream outage'),
        ('ok','#45d1ad','Energized'),
    ]:
        group = [n for n in result['nodes'] if
                 ('failed' if n['failed'] else 'outage' if n['offline'] else 'ok')==state]
        if not group:
            continue
        fig.add_trace(go.Scatter(
            x=[n['x'] for n in group],y=[n['y'] for n in group],
            text=[n['name'].replace(' Demo ','<br>Demo ') for n in group],
            customdata=[[n['id'], n['state'], n['customers']] for n in group],
            mode='markers+text',name=name, textposition='top center',
            textfont=dict(size=9,color='#daeef0'),
            marker=dict(color=fill,size=[28 if n['type']=='Substation' else 23 if n['type']=='Feeder' else 18 for n in group],
                        line=dict(width=2,color='#092336')),
            hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]}'
                          '<br>Customers: %{customdata[2]:,}<extra></extra>',
        ))
    fig.update_layout(
        height=480, margin=dict(t=25,b=10,l=5,r=5),
        xaxis=dict(visible=False,range=[0.0,5.45]),
        yaxis=dict(visible=False,range=[-3.2,6.0]),
        paper_bgcolor='#10283b',plot_bgcolor='#10283b',
        font=dict(color='#cdebee'),
        legend=dict(orientation='h',yanchor='bottom',y=1.00,xanchor='left',x=0.02,bgcolor='rgba(9,21,36,.6)'),
    )
    return fig


# ----- Sidebar and scenario controls -----
st.sidebar.markdown('### 🐞 GridHive / the Anthill')
st.sidebar.caption('Simulation control deck · Semifinals prototype')
# Reset must be before keyed widgets are rendered.
st.sidebar.button('↺ Reset entire demo',on_click=reset_demo,use_container_width=True)
st.sidebar.divider()
st.sidebar.selectbox('Storm strength',list(STORMS),index=3,key='storm')
st.sidebar.selectbox('Approximate landfall',list(TRACKS),index=0,key='track')
st.sidebar.toggle('Simulate grid component failures',value=True,key='simulate_faults',
                  help='Models hypothetical outages based on invented hazard thresholds; no real utility telemetry.')
st.sidebar.divider()
st.sidebar.markdown('**Data integrity**')
st.sidebar.info('All grid assets, customers, hazard values and economics are synthetic. Only manually uploaded inspection images/notes are user supplied.')
st.sidebar.caption('No live utility data · No real robot controls · Not for dispatch decisions')

try:
    records = list_inspections(limit=200)
except Exception as exc:
    st.error('The local inspection database could not be opened. Ensure the app has a writable data directory.')
    st.exception(exc)
    st.stop()

result = simulate(st.session_state['storm'], st.session_state['track'],records,
                  st.session_state['simulate_faults'])
node_by_id = {n['id']: n for n in result['nodes']}

st.markdown('''<div class="hero"><div class="hero-cap">GRIDHIVE · STORM-READY INFRASTRUCTURE</div>
<div class="hero-title">the Anthill <span style="color:#6eebca">/ command center</span></div>
<div class="hero-lead">From robotic inspection to explainable restoration priorities.</div></div>''',unsafe_allow_html=True)
flash()
a,b,c,d = st.columns(4)
a.metric('GRID ASSETS',len(result['nodes']))
b.metric('SIMULATED FAILURES',result['failed_assets'])
c.metric('CUSTOMERS AFFECTED',f"{result['affected_customers']:,}")
d.metric('CRITICAL SERVICES',result['critical_facilities_affected'])
st.caption('⚠️ Fictional scenario data · Simulated electrical network · Not actual utility status')

tabs = st.tabs(['🏠 Overview','🌀 Storm Lab','📷 Inspections','🧠 Restoration AI','🔌 Grid Twin','📊 Impact'])

with tabs[0]:
    left,right = st.columns([1.5,1],gap='large')
    with left:
        st.subheader('Florida infrastructure risk map')
        st.plotly_chart(map_chart(result),use_container_width=True,key='home_map')
        st.caption('Markers show simulated asset risk. Lines represent a simplified, fictional grid topology.')
    with right:
        st.subheader('What needs attention')
        st.markdown(f'<div class="info-tile"><b>{result["storm"]} · {result["track"]}</b>'
                    f'<p>{result["avg_hazard"]}/100 average modeled hazard • {result["offline_assets"]} modeled offline assets</p></div>',
                    unsafe_allow_html=True)
        for q in result['queue'][:4]:
            st.markdown(f'**{q["action"]}: {q["asset"]}**  '
                        f'  \nPriority {q["score"]:.1f}/100 · Restorable customers {q["customers_restored"]:,}')
            st.divider()
        if not result['queue']:
            st.success('No modeled repair or elevated inspection action at this threshold.')
        st.markdown('<div class="note">A complete demo: choose a storm → submit an inspection → see restoration rankings and outage impacts update.</div>',unsafe_allow_html=True)

with tabs[1]:
    st.subheader('Hurricane scenario simulator')
    st.write('Change the strength or landfall location in the **left sidebar**. The modeled hazard, outages, map, queue, and impact calculations all update together.')
    st.warning('This is a deliberately simplified synthetic scenario, not a forecast or measured flood/wind probability.')
    col1,col2 = st.columns([1.15,.85])
    with col1:
        frame=pd.DataFrame(result['nodes']).sort_values('severity',ascending=False)
        colors=[RISK_COLORS[r] for r in frame['risk']]
        fig=go.Figure(go.Bar(x=frame['severity'],y=frame['name'],orientation='h',marker_color=colors,
                             hovertemplate='%{y}: %{x:.1f}/100<extra></extra>'))
        fig.update_layout(height=505,margin=dict(l=0,r=5,t=10,b=5),
                          paper_bgcolor='#10283b',plot_bgcolor='#10283b',font_color='#d0e8ea',
                          xaxis=dict(range=[0,100],title='Simulated hazard score'),yaxis=dict(autorange='reversed'))
        st.plotly_chart(fig,use_container_width=True)
    with col2:
        st.markdown('#### Hazard drivers')
        st.write('The model combines baseline vulnerability with wind, flood, vegetation, and approximate distance from the selected landfall point.')
        st.markdown('**How to present it:**')
        st.markdown('1. Choose Category 1, then Category 5.\n2. Change the landfall region.\n3. Show how the threatened assets change.\n4. Add one inspection to change the repair plan.')
        if st.button('🪲 Simulate TerraBeetle damage report',use_container_width=True):
            save_inspection('MIA-F2','Confirmed damage',92,'Demo simulation',
                            'SYNTHETIC TerraBeetle demo report: tree damage observed at Doral feeder. '
                            'Not a real sensor or camera observation.')
            st.session_state['flash']='Synthetic TerraBeetle damage report inserted. Check Inspections and Grid Twin.'
            st.rerun()

with tabs[2]:
    st.subheader('Robot inspection intake')
    st.write('Upload a real photo or enter a manual report. A **confirmed damage** report updates the modeled risk and network immediately; an inspection is never classified as verified by AI alone.')
    left,right=st.columns([1,1],gap='large')
    with left:
        with st.form('new_inspection',clear_on_submit=True):
            target=st.selectbox('Grid asset',[n['id'] for n in result['nodes']],
                                format_func=lambda aid: node_by_id[aid]['name'])
            status=st.selectbox('Human inspection result',
                                ['Needs review','Confirmed damage','No visible damage','Repaired / restored'])
            severity=st.slider('Observed severity (if damaged)',0,100,85)
            confidence=st.selectbox('Evidence confidence',['Unverified','Low','Medium','High'])
            notes=st.text_area('Inspection notes',height=110,
                placeholder='Observed conditions, potential failure, date/time and safety notes…')
            photo=st.file_uploader('Optional JPEG/PNG image (up to 5 MB)',type=['jpg','jpeg','png'])
            submitted=st.form_submit_button('Save inspection and update the Anthill',use_container_width=True)
        if submitted:
            try:
                image_bytes=optimized_photo(photo)
                save_inspection(target,status,severity,confidence,notes.strip() or 'No notes supplied',
                                photo.name if photo else None,image_bytes)
                st.session_state['flash']=f'Inspection saved for {node_by_id[target]["name"]}; all simulation views recalculated.'
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f'Could not save the inspection: {exc}')
    with right:
        st.markdown('#### Latest inspection evidence')
        if not records:
            st.info('No reports yet. Submit an inspection, or use the synthetic TerraBeetle button in Storm Lab.')
        else:
            options=[r['id'] for r in records]
            rec_by_id={r['id']:r for r in records}
            rec_id=st.selectbox('Select report',options,
                     format_func=lambda i: f"#{i} · {node_by_id.get(rec_by_id[i]['asset_id'],{}).get('name',rec_by_id[i]['asset_id'])} · {rec_by_id[i]['status']}")
            rec=rec_by_id[rec_id]
            st.markdown(f'**Result:** {rec["status"]} · **Confidence:** {rec["confidence"]}')
            st.write(f'**Notes:** {rec["notes"]}')
            st.caption(f'Recorded: {rec["created_at"]} UTC · Source: human input or labeled simulation')
            if rec['image_name']:
                data=find_image(rec_id)
                if data:
                    st.image(data,caption=rec['image_name'],use_container_width=True)
                    if get_api_key():
                        allow=st.checkbox('I consent to send this uploaded image to Google Gemini for an unverified visual description.')
                        if st.button('Analyze image with Gemini',disabled=not allow):
                            try:
                                with st.spinner('Examining image...'):
                                    answer=ask_gemini(
                                        'Describe only visible conditions in this electrical infrastructure inspection photo. '
                                        'State uncertainties and do not claim a component is unsafe or operational. '
                                        'Do not issue physical repair instructions. Provide short bullet observations.',data)
                                st.info('**AI assistance — unverified, not a safety determination**')
                                st.write(answer)
                            except Exception as exc:
                                st.error(f'AI image description unavailable: {exc}')
                    else:
                        st.caption('Optional Gemini vision requires a GEMINI_API_KEY. Photos are never sent to an AI service without consent.')
                else:
                    st.caption('Image thumbnail is unavailable in this environment.')
    if records:
        st.markdown('#### Inspection log')
        st.dataframe(pd.DataFrame([{
            'Time (UTC)':r['created_at'],'Asset':node_by_id.get(r['asset_id'],{}).get('name',r['asset_id']),
            'Result':r['status'],'Severity':r['severity'],'Confidence':r['confidence'],
            'Photo': 'Yes' if r['image_name'] else 'No',
        } for r in records]),use_container_width=True,hide_index=True)

with tabs[3]:
    st.subheader('Explainable restoration decision support')
    st.markdown('The queue distinguishes **repair** jobs from **preventive inspections**, and computes how many customers a single hypothetical repair could immediately restore without assuming every other fault is fixed.')
    if result['queue']:
        jobs=pd.DataFrame([{**{key:item[key] for key in ['asset','action','score','customers_restored','critical_services','estimated_hours']},
                            'Status':'Blocked by another fault' if item['blocked'] else 'Actionable'}
                          for item in result['queue']])
        jobs=jobs.rename(columns={'asset':'Asset','action':'Action','score':'Priority /100',
            'customers_restored':'Customers restored if repaired','critical_services':'Critical services restored',
            'estimated_hours':'Repair hours (assumed)'})
        st.dataframe(jobs,hide_index=True,use_container_width=True)
        chosen=st.selectbox('Explain a recommendation',[q['asset_id'] for q in result['queue']],
                            format_func=lambda v: node_by_id[v]['name'])
        recommendation=next(q for q in result['queue'] if q['asset_id']==chosen)
        st.markdown(f'<div class="info-tile"><b>{recommendation["action"]}: {recommendation["asset"]}</b>'
                    f'<p>{recommendation["reason"]}</p></div>',unsafe_allow_html=True)
        st.caption('Weights are invented for demonstration and have not been trained or validated on utility decisions. All field work requires human authorization.')
    else:
        st.success('No repair or high-priority inspection recommendation in the current demo scenario.')
    st.markdown('#### Incident briefing')
    st.text_area('Transparent rule-based summary (always available)',briefing(result),height=245)
    if get_api_key():
        if st.button('✨ Generate AI-assisted executive briefing'):
            facts={'storm':result['storm'],'track':result['track'],'failed':result['failed_assets'],
                   'affected_customers':result['affected_customers'],
                   'critical_facilities':result['critical_facilities_affected'],
                   'top_actions':result['queue'][:4]}
            prompt=('You are drafting an executive summary for a FICTIONAL hurricane-grid student demo. '
                    'Use ONLY the JSON-like facts supplied. Distinguish simulation from verified observations. '
                    'Do not invent cost savings, sensor results or field dispatches. Explain top actions in 170 words '
                    'and note that utility experts must validate recommendations.\n' + str(facts))
            try:
                with st.spinner('Generating briefing...'):
                    st.session_state['ai_briefing']=ask_gemini(prompt)
            except Exception as exc:
                st.warning(f'Gemini unavailable: {exc}. Rule-based summary remains available.')
        if st.session_state.get('ai_briefing'):
            st.markdown('**AI-assisted summary (not independently verified)**')
            st.write(st.session_state['ai_briefing'])
    else:
        st.info('Optional Gemini AI briefing: add GEMINI_API_KEY as a deployment secret. The local, explainable scoring and briefing work without it.')

with tabs[4]:
    st.subheader('Grid Digital Twin · upstream/downstream impact')
    st.write('Fictional substations → feeders → transformers. A component outage also de-energizes downstream nodes until the relevant upstream fault is resolved.')
    st.plotly_chart(grid_graph(result),use_container_width=True)
    a,b,c=st.columns(3)
    a.metric('Direct modeled failures',result['failed_assets'])
    b.metric('De-energized nodes',result['offline_assets'])
    c.metric('Customers downstream of outages',f"{result['affected_customers']:,}")
    if result['direct_failures']:
        st.markdown('#### Simulate a repair completing')
        fault=st.selectbox('Select a failed component to mark restored',result['direct_failures'],
                           format_func=lambda aid: node_by_id[aid]['name'])
        if st.button('Mark selected component as restored',use_container_width=True):
            save_inspection(fault,'Repaired / restored',0,'Demo simulation',
                            'SYNTHETIC demo repair completion; no physical equipment was switched.')
            st.session_state['flash']='Simulated repair recorded. Network and customer outage metrics recalculated.'
            st.rerun()
    st.dataframe(pd.DataFrame([{
        'Asset':n['name'],'Type':n['type'],'Network condition':n['state'],
        'Customers served':n['customers'],'Critical facility':n['critical_facility'],
    } for n in result['nodes']]),hide_index=True,use_container_width=True)

with tabs[5]:
    st.subheader('Economic, community & environmental impact')
    st.caption('Sensitivity analysis based entirely on adjustable demo assumptions. No real savings are measured or promised.')
    p1,p2=st.columns(2,gap='large')
    with p1:
        hours=st.slider('Assumed outage duration (hours)',1,96,12)
        unit_cost=st.number_input('Assumed economic cost per customer-hour ($)',min_value=0.0,max_value=500.0,value=8.0,step=1.0)
        potential_savings=st.slider('Hypothetical outage-duration improvement (%)',0,70,15)
    with p2:
        diesel_rate=st.number_input('Assumed diesel use per impacted critical facility (liters/hour)',
                                     min_value=0.0,max_value=500.0,value=8.0,step=1.0)
        carbon_rate=st.number_input('Assumed kg CO₂ per diesel liter',min_value=0.0,max_value=10.0,value=2.68,step=0.01)
        st.info('The improvement slider is a **what-if target**, not a tested benefit of GridHive.')
    impact=economic_impact(result,hours,unit_cost,potential_savings,diesel_rate,carbon_rate)
    a,b,c=st.columns(3)
    a.metric('Modeled customer outage-hours',f"{impact['outage_customer_hours']:,}")
    b.metric('Scenario economic exposure',f"${impact['scenario_cost']:,.0f}")
    c.metric('Critical-service locations at risk',result['critical_facilities_affected'])
    a,b=st.columns(2)
    a.metric('Hypothetical avoided cost',f"${impact['hypothetical_avoided_cost']:,.0f}")
    b.metric('Illustrative diesel CO₂ emissions',f"{impact['diesel_co2_kg']:,.0f} kg")
    fig=go.Figure(data=[go.Bar(name='Baseline scenario',x=['Customer outage-hours'],y=[impact['outage_customer_hours']],marker_color='#ed7b82'),
                            go.Bar(name='What-if improved response',x=['Customer outage-hours'],
                                   y=[impact['outage_customer_hours']-impact['hypothetical_reduced_hours']],marker_color='#43cfa8')])
    fig.update_layout(barmode='group',height=330,paper_bgcolor='#10283b',plot_bgcolor='#10283b',
                      font_color='#cce9e8',margin=dict(l=0,r=0,t=15,b=0))
    st.plotly_chart(fig,use_container_width=True)
    st.caption('Customer counts are non-overlapping fictional service allocations. Diesel emissions assume affected critical-service locations run generators for the entire chosen duration; GridHive has not demonstrated emissions reductions.')

st.divider()
st.caption('GridHive · the Anthill V2 | HackSTEM prototype | No verified grid data, no automated dispatch or actuation | Built for demonstration only')
