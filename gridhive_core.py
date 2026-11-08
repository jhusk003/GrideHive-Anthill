"""GridHive synthetic restoration and hurricane model."""

from math import hypot

# Customers belong only to terminal service zones.
# This prevents double counting upstream feeder customers.

ASSETS = [
    dict(id="M-S", name="Miami substation", region="Miami",
         kind="Substation", parent=None, lat=25.774, lon=-80.218,
         customers=0, base=33, wind=.90, flood=.90,
         critical=95, repair_h=9),

    dict(id="M-F", name="Miami feeder", region="Miami",
         kind="Feeder", parent="M-S", lat=25.785, lon=-80.239,
         customers=0, base=38, wind=.85, flood=.75,
         critical=80, repair_h=5),

    dict(id="M-A", name="Downtown service zone", region="Miami",
         kind="Service zone", parent="M-F", lat=25.779, lon=-80.196,
         customers=1450, base=30, wind=.80, flood=.95,
         critical=98, repair_h=3),

    dict(id="M-B", name="West Miami service zone", region="Miami",
         kind="Service zone", parent="M-F", lat=25.761, lon=-80.290,
         customers=980, base=25, wind=.78, flood=.60,
         critical=65, repair_h=3),

    dict(id="T-S", name="Tampa substation", region="Tampa",
         kind="Substation", parent=None, lat=27.951, lon=-82.457,
         customers=0, base=34, wind=.92, flood=.85,
         critical=91, repair_h=9),

    dict(id="T-F", name="Tampa feeder", region="Tampa",
         kind="Feeder", parent="T-S", lat=27.972, lon=-82.430,
         customers=0, base=35, wind=.85, flood=.82,
         critical=79, repair_h=5),

    dict(id="T-A", name="Tampa service zone", region="Tampa",
         kind="Service zone", parent="T-F", lat=27.981, lon=-82.409,
         customers=1120, base=27, wind=.79, flood=.88,
         critical=83, repair_h=3),

    dict(id="O-S", name="Orlando substation", region="Orlando",
         kind="Substation", parent=None, lat=28.540, lon=-81.380,
         customers=0, base=28, wind=.72, flood=.60,
         critical=87, repair_h=8),

    dict(id="O-F", name="Orlando feeder", region="Orlando",
         kind="Feeder", parent="O-S", lat=28.563, lon=-81.370,
         customers=0, base=29, wind=.70, flood=.54,
         critical=72, repair_h=4),

    dict(id="O-A", name="Orlando service zone", region="Orlando",
         kind="Service zone", parent="O-F", lat=28.570, lon=-81.342,
         customers=1320, base=23, wind=.68, flood=.55,
         critical=78, repair_h=3),

    dict(id="J-S", name="Jacksonville substation",
         region="Jacksonville", kind="Substation", parent=None,
         lat=30.330, lon=-81.660, customers=0, base=29,
         wind=.85, flood=.76, critical=89, repair_h=8),

    dict(id="J-F", name="Jacksonville feeder",
         region="Jacksonville", kind="Feeder", parent="J-S",
         lat=30.347, lon=-81.647, customers=0, base=31,
         wind=.80, flood=.73, critical=76, repair_h=5),

    dict(id="J-A", name="Jacksonville service zone",
         region="Jacksonville", kind="Service zone", parent="J-F",
         lat=30.354, lon=-81.620, customers=880, base=26,
         wind=.78, flood=.75, critical=75, repair_h=3),
]

TRACKS = {
    "Miami coast": (25.77, -80.20),
    "Tampa Bay": (27.95, -82.46),
    "Central Florida": (28.54, -81.38),
    "North Florida": (30.33, -81.66),
}


def scenario(category=4, track="Miami coast",
             verified=None, extra_failures=None):

    verified = verified or {}
    extra_failures = set(extra_failures or [])
    center = TRACKS[track]
    nodes = []

    for asset in ASSETS:
        distance = hypot(
            (asset["lat"] - center[0]) * 111,
            (asset["lon"] - center[1]) * 99
        )

        proximity = max(0.0, 1.0 - distance / 95.0)

        storm_add = category * (
            5.3 * asset["wind"] + 4.8 * asset["flood"]
        ) * (0.12 + 0.88 * proximity)

        risk = min(
            100,
            round(
                max(
                    asset["base"] + storm_add,
                    verified.get(asset["id"], 0)
                ),
                1
            )
        )

        direct_failed = (
            risk >= 69 or asset["id"] in extra_failures
        )

        nodes.append(dict(
            asset,
            risk=risk,
            direct_failed=direct_failed
        ))

    return nodes


def outage_states(nodes, repaired=()):
    repaired = set(repaired)
    states = {}

    for n in nodes:
        direct = (
            n["direct_failed"] and
            n["id"] not in repaired
        )

        upstream = bool(
            n["parent"] and
            states[n["parent"]]["offline"]
        )

        states[n["id"]] = {
            "offline": direct or upstream,
            "direct": direct,
            "status": (
                "Failed" if direct
                else "Upstream outage" if upstream
                else "Energized"
            )
        }

    return states


def affected_customers(nodes, repaired=()):
    states = outage_states(nodes, repaired)

    return sum(
        n["customers"]
        for n in nodes
        if n["customers"] and states[n["id"]]["offline"]
    )


def repair_gain(nodes, asset_id, repaired=()):
    before = affected_customers(nodes, repaired)
    after = affected_customers(
        nodes, set(repaired) | {asset_id}
    )

    return max(0, before - after)


def repair_plan(nodes, strategy="Balanced"):
    failed = [
        n for n in nodes if n["direct_failed"]
    ]

    repaired = set()
    schedule = []
    customer_hours = 0.0
    elapsed = 0.0

    while len(repaired) < len(failed):
        candidates = [
            n for n in failed
            if n["id"] not in repaired
        ]

        current = affected_customers(nodes, repaired)
        scored = []

        for n in candidates:
            gain = repair_gain(
                nodes, n["id"], repaired
            )

            hours = n["repair_h"]

            if strategy == "Customers first":
                score = gain * 100 + n["critical"]

            elif strategy == "Fastest restoration":
                score = gain / hours + 0.01 / hours

            elif strategy == "Critical facilities":
                score = (
                    gain * (0.3 + n["critical"] / 100)
                    + n["critical"] * 2
                )

            else:
                score = (
                    gain * (
                        0.55 + n["critical"] / 150
                    ) / hours
                    + n["risk"] * 0.4
                )

            scored.append((score, n, gain))

        _, chosen, gain = max(
            scored,
            key=lambda x: (
                x[0], x[2], x[1]["id"]
            )
        )

        duration = chosen["repair_h"]

        customer_hours += current * duration
        elapsed += duration
        repaired.add(chosen["id"])

        schedule.append({
            "asset": chosen["name"],
            "id": chosen["id"],
            "hours": duration,
            "restored": gain,
            "finished_h": elapsed,
            "affected_after": affected_customers(
                nodes, repaired
            )
        })

    return {
        "strategy": strategy,
        "schedule": schedule,
        "customer_hours": round(customer_hours),
        "total_hours": elapsed,
        "initial_affected": affected_customers(nodes)
    }


def verified_max(records):
    result = {}

    for rec in records:
        if rec["verified"]:
            asset_id = rec["asset_id"]
            result[asset_id] = max(
                result.get(asset_id, 0),
                rec["severity"]
            )

    return result


def summary(nodes, plan):
    top = (
        plan["schedule"][0]
        if plan["schedule"] else None
    )

    text = (
        "SIMULATED INCIDENT BRIEF | "
        f"{plan['initial_affected']:,} unique "
        "customers affected. "
    )

    if top:
        text += (
            f"Suggested first repair: {top['asset']}, "
            f"with {top['restored']:,} customers "
            f"restored after {top['hours']} "
            "illustrative repair hours. "
        )
    else:
        text += "No modeled failures requiring repair. "

    return text + (
        "Scores are hypothetical. Confirm field "
        "conditions, crew safety, critical facilities, "
        "and approvals before real-world action."
    )