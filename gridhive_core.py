"""Deterministic, fictional hurricane-grid simulation for the GridHive demo.

Not a utility-grade hazard forecast, restoration optimizer, or live telemetry feed.
"""
from __future__ import annotations
from copy import deepcopy
from math import asin, cos, radians, sin, sqrt

# All nodes, customers, links, critical services and exposures are FICTIONAL demo data.
ASSETS = [
    dict(id='MIA-S1', name='Miami Demo Substation', type='Substation', lat=25.775, lon=-80.192,
         customers=0, criticality=97, urgency=91, vulnerability=72, wind=93, flood=90, vegetation=32,
         restoration_hours=14, crews=3, critical_facility='None', x=1.2, y=3.9),
    dict(id='MIA-F1', name='Downtown Demo Feeder', type='Feeder', lat=25.785, lon=-80.208,
         customers=1200, criticality=95, urgency=85, vulnerability=65, wind=89, flood=82, vegetation=40,
         restoration_hours=7, crews=2, critical_facility='Hospital district', x=2.6, y=5.1),
    dict(id='MIA-T1', name='Brickell Demo Transformer', type='Transformer', lat=25.763, lon=-80.193,
         customers=450, criticality=89, urgency=75, vulnerability=69, wind=94, flood=88, vegetation=28,
         restoration_hours=4, crews=1, critical_facility='Community clinic', x=4.2, y=5.1),
    dict(id='MIA-F2', name='Doral Demo Feeder', type='Feeder', lat=25.819, lon=-80.352,
         customers=1700, criticality=70, urgency=70, vulnerability=62, wind=83, flood=38, vegetation=77,
         restoration_hours=8, crews=2, critical_facility='None', x=2.6, y=3.1),
    dict(id='MIA-T2', name='Westchester Demo Transformer', type='Transformer', lat=25.747, lon=-80.317,
         customers=350, criticality=59, urgency=51, vulnerability=60, wind=69, flood=55, vegetation=68,
         restoration_hours=5, crews=1, critical_facility='None', x=4.2, y=3.1),
    dict(id='BWR-S1', name='Broward Demo Substation', type='Substation', lat=26.118, lon=-80.141,
         customers=0, criticality=94, urgency=84, vulnerability=66, wind=90, flood=78, vegetation=35,
         restoration_hours=12, crews=3, critical_facility='None', x=1.2, y=1.1),
    dict(id='BWR-F1', name='Fort Lauderdale Demo Feeder', type='Feeder', lat=26.125, lon=-80.152,
         customers=2600, criticality=84, urgency=74, vulnerability=64, wind=91, flood=80, vegetation=64,
         restoration_hours=9, crews=2, critical_facility='Emergency shelter', x=2.6, y=1.4),
    dict(id='BWR-T1', name='Sunrise Demo Transformer', type='Transformer', lat=26.154, lon=-80.295,
         customers=610, criticality=52, urgency=49, vulnerability=46, wind=76, flood=31, vegetation=65,
         restoration_hours=4, crews=1, critical_facility='None', x=4.2, y=1.4),
    dict(id='KEY-S1', name='Keys Demo Substation', type='Substation', lat=25.087, lon=-80.446,
         customers=0, criticality=96, urgency=98, vulnerability=77, wind=99, flood=99, vegetation=26,
         restoration_hours=16, crews=3, critical_facility='None', x=1.2, y=-1.0),
    dict(id='KEY-F1', name='Key Largo Demo Feeder', type='Feeder', lat=25.095, lon=-80.440,
         customers=2100, criticality=96, urgency=95, vulnerability=83, wind=98, flood=97, vegetation=48,
         restoration_hours=10, crews=2, critical_facility='Emergency shelter', x=2.6, y=-1.0),
    dict(id='KEY-T1', name='Tavernier Demo Transformer', type='Transformer', lat=25.011, lon=-80.515,
         customers=470, criticality=77, urgency=79, vulnerability=80, wind=95, flood=98, vegetation=55,
         restoration_hours=6, crews=1, critical_facility='Medical facility', x=4.2, y=-1.0),
    dict(id='HOM-S1', name='Homestead Demo Substation', type='Substation', lat=25.468, lon=-80.477,
         customers=0, criticality=86, urgency=78, vulnerability=63, wind=86, flood=68, vegetation=48,
         restoration_hours=11, crews=3, critical_facility='None', x=1.2, y=-2.6),
    dict(id='HOM-F1', name='South Dade Demo Feeder', type='Feeder', lat=25.498, lon=-80.478,
         customers=900, criticality=85, urgency=85, vulnerability=71, wind=87, flood=69, vegetation=73,
         restoration_hours=8, crews=2, critical_facility='Water treatment', x=2.6, y=-2.6),
    dict(id='HOM-T1', name='Florida City Demo Transformer', type='Transformer', lat=25.452, lon=-80.483,
         customers=380, criticality=58, urgency=61, vulnerability=58, wind=82, flood=65, vegetation=61,
         restoration_hours=5, crews=1, critical_facility='None', x=4.2, y=-2.6),
]

# Parent node -> directly downstream node. DAG by construction.
LINKS = [
    ('MIA-S1', 'MIA-F1'), ('MIA-F1', 'MIA-T1'), ('MIA-S1', 'MIA-F2'), ('MIA-F2', 'MIA-T2'),
    ('BWR-S1', 'BWR-F1'), ('BWR-F1', 'BWR-T1'),
    ('KEY-S1', 'KEY-F1'), ('KEY-F1', 'KEY-T1'),
    ('HOM-S1', 'HOM-F1'), ('HOM-F1', 'HOM-T1'),
]

STORMS = {'Normal': 0, 'Tropical storm': 29, 'Category 1': 47, 'Category 3': 72, 'Category 5': 100}
TRACKS = {
    'Miami coast': (25.77, -80.17),
    'Fort Lauderdale': (26.12, -80.12),
    'Florida Keys': (25.09, -80.40),
    'Homestead': (25.47, -80.48),
}
RISK_COLORS = {'Low': '#38cda7', 'Elevated': '#f4b85a', 'Critical': '#fb687d'}


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles."""
    a, b, c, d = map(radians, [lat1, lon1, lat2, lon2])
    delta = sin((c-a)/2)**2 + cos(a)*cos(c)*sin((d-b)/2)**2
    return 3958.8 * 2 * asin(min(1, sqrt(delta)))


def _network_status(direct_failure):
    """Iteratively propagate outages downstream, preserving causal distinction."""
    offline = set(direct_failure)
    changed = True
    while changed:
        before = len(offline)
        for parent, child in LINKS:
            if parent in offline:
                offline.add(child)
        changed = len(offline) != before
    return offline


def _risk_label(score):
    return 'Critical' if score >= 75 else 'Elevated' if score >= 50 else 'Low'


def simulate(storm='Category 3', track='Miami coast', inspections=None, simulate_failures=True):
    """Return recomputed hazards, downstream outages and an explainable action queue.

    inspections: iterable of {'asset_id','status','severity',...}; most recent first.
    """
    if storm not in STORMS:
        raise ValueError('Unknown storm')
    if track not in TRACKS:
        raise ValueError('Unknown track')
    intensity = STORMS[storm]
    center_lat, center_lon = TRACKS[track]
    latest = {}
    for record in inspections or []:
        aid = record.get('asset_id')
        if aid and aid not in latest:
            latest[aid] = record
    nodes = deepcopy(ASSETS)
    direct_failures = set()
    for node in nodes:
        distance = haversine_miles(node['lat'], node['lon'], center_lat, center_lon)
        proximity = max(0.16, 1.0 - distance / 125)
        wind_score = intensity * node['wind'] / 100 * (0.62 + 0.38*proximity)
        flood_score = intensity * node['flood'] / 100 * (0.28 + 0.72*proximity)
        veg_score = intensity * node['vegetation'] / 100 * (0.35 + 0.65*proximity)
        # Transparent, invented demonstration coefficients, not a forecast model.
        hazard = min(100, round(
            0.28*node['vulnerability'] + 0.52*wind_score + 0.25*flood_score + 0.13*veg_score,
            1,
        ))
        observed = latest.get(node['id'])
        status = observed.get('status') if observed else 'Not inspected'
        if status == 'Confirmed damage':
            hazard = max(hazard, 85.0, float(observed.get('severity', 85)))
        elif status in ('No visible damage', 'Repaired / restored'):
            # Still potentially vulnerable, but a verified visual check overrides
            # the hypothetical component failure (not an upstream outage).
            hazard = min(hazard, 69.0)
        node.update(
            distance_miles=round(distance, 1), wind_index=round(wind_score, 1),
            flood_index=round(flood_score, 1), vegetation_index=round(veg_score, 1),
            severity=round(hazard, 1), risk=_risk_label(hazard),
            inspection_status=status,
        )
        if status == 'Confirmed damage' or (status not in ('No visible damage', 'Repaired / restored') and simulate_failures and intensity > 0 and hazard >= 76):
            direct_failures.add(node['id'])
    offline = _network_status(direct_failures)
    total_customers = sum(n['customers'] for n in nodes)
    affected_customers = sum(n['customers'] for n in nodes if n['id'] in offline)
    for node in nodes:
        node['failed'] = node['id'] in direct_failures
        node['offline'] = node['id'] in offline
        node['state'] = ('Damaged (simulated or reported)' if node['failed'] else
                         'Without power (upstream)' if node['offline'] else 'Energized (simulated)')
        node['risk_score'] = node['severity']

    queue = []
    for node in nodes:
        if node['failed']:
            repaired_state = _network_status(direct_failures - {node['id']})
            newly_served = sum(
                n['customers'] for n in nodes if n['id'] in offline and n['id'] not in repaired_state
            )
            restored_facilities = [
                n['critical_facility'] for n in nodes
                if n['id'] in offline and n['id'] not in repaired_state and n['critical_facility'] != 'None'
            ]
            customer_pct = 100 * newly_served / max(1, total_customers)
            score = round(
                0.40*customer_pct + 0.25*node['criticality']
                + 0.20*node['severity'] + 0.15*node['urgency'], 1,
            )
            why = (
                f"Repair candidate. Could restore {newly_served:,} customers immediately "
                f"if this is the only repair performed, including {len(restored_facilities)} critical-service locations. "
                f"Weighted score = 40% share of customers restored + 25% criticality "
                f"+ 20% severity + 15% urgency."
            )
            queue.append(dict(
                asset_id=node['id'], asset=node['name'], action='Repair',
                score=score, customers_restored=newly_served, critical_services=len(restored_facilities),
                estimated_hours=node['restoration_hours'], crews=node['crews'],
                blocked=(newly_served == 0), reason=why, risk=node['risk'],
            ))
        elif node['severity'] >= 43 and node['inspection_status'] == 'Not inspected':
            score = round(
                0.40*node['severity'] + 0.25*node['criticality']
                + 0.20*(100*node['customers']/max(1, total_customers)) + 0.15*node['urgency'], 1,
            )
            queue.append(dict(
                asset_id=node['id'], asset=node['name'], action='Inspect', score=score,
                customers_restored=0, critical_services=0, estimated_hours=0, crews=0,
                blocked=False, risk=node['risk'],
                reason=(f"Preventive inspection recommended. Hazard {node['severity']:.1f}/100; "
                        f"criticality {node['criticality']}/100; wind exposure {node['wind']}/100; "
                        f"flood exposure {node['flood']}/100. No failure has been confirmed."),
            ))
    queue.sort(key=lambda q: (
        0 if q['action'] == 'Repair' and not q['blocked'] else
        1 if q['action'] == 'Repair' else 2,
        -q['score'],
    ))
    return dict(
        nodes=nodes, queue=queue, direct_failures=sorted(direct_failures),
        offline=sorted(offline), storm=storm, track=track,
        total_customers=total_customers, affected_customers=affected_customers,
        offline_assets=len(offline), failed_assets=len(direct_failures),
        critical_facilities_affected=len({n['critical_facility'] for n in nodes if n['offline'] and n['critical_facility']!='None'}),
        avg_hazard=round(sum(n['severity'] for n in nodes)/len(nodes), 1),
    )


def economic_impact(result, duration_hours, customer_hour_cost, reduction_pct=0, diesel_liters_per_hour=0, co2_per_liter=2.68):
    """Illustrative economic/social/environmental scenarios, not validated savings."""
    affected = result['affected_customers']
    outage_hours = affected * duration_hours
    base_cost = outage_hours * customer_hour_cost
    improvement = max(0, min(100, reduction_pct)) / 100
    saved_hours = outage_hours * improvement
    generators_count = result['critical_facilities_affected']
    diesel_liters = generators_count * duration_hours * diesel_liters_per_hour
    return dict(
        outage_customer_hours=round(outage_hours), scenario_cost=round(base_cost, 2),
        hypothetical_reduced_hours=round(saved_hours),
        hypothetical_avoided_cost=round(base_cost*improvement, 2),
        diesel_liters=round(diesel_liters, 1), diesel_co2_kg=round(diesel_liters*co2_per_liter, 1),
    )


def briefing(result):
    """Reliable non-LLM fallback, always labeled as rule-based."""
    actions = result['queue'][:3]
    opening = (f"{result['storm']} centered near {result['track']} is a synthetic test scenario. "
               f"The simulation shows {result['failed_assets']} directly failed components and "
               f"{result['affected_customers']:,} potentially affected customers. "
               f"{result['critical_facilities_affected']} modeled critical-service locations are downstream of outages.")
    lines = [opening]
    if actions:
        for idx, item in enumerate(actions, 1):
            lines.append(f"{idx}. {item['action']} {item['asset']}: {item['reason']}")
    else:
        lines.append('No immediate repair/inspection action exceeds the demo thresholds.')
    lines.append('All scores and recommended actions require trained utility review; no equipment control is performed.')
    return '\n\n'.join(lines)
