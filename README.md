# GridHive — the Anthill V2

A **synthetic**, educational HackSTEM hurricane-resilience prototype. No live utility data or robotic control.

## Six integrated capabilities

1. Hurricane simulator: storm category and approximate landfall influence synthetic risk and outages.
2. Inspection intake: manually uploaded photos/notes and confirmed damage update the model and repair queue.
3. Explainable restoration planner: transparent ranking and optional Gemini-assisted incident briefing.
4. Grid digital twin: fictional feeder/substation/transformer connections and downstream outage effects.
5. Community and economic impact: adjustable outage-hour, cost, and illustrative emissions assumptions.
6. Polished command center: responsive Streamlit dashboard, maps, tabs, and a demo reset.

## Run locally (Windows PowerShell)

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m streamlit run app.py
```

## Test

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Deploy

- Streamlit Community Cloud: connect this repository and set `app.py` as the entry point.
- Render: connect this repository as a Web Service and use `render.yaml` (Blueprint), or the start command in that file.

Optional Gemini key: `GEMINI_API_KEY` in your hosting platform's secrets/environment settings, **never in Git**. Without it, the app provides rule-based summaries. Only send an uploaded photo to Gemini with consent.

## Data and safety

- All grid topology, asset names, locations, customer counts, damage estimates, and financial numbers are illustrative.
- SQLite records persist locally; free cloud hosting often has ephemeral filesystems, so data may reset across restarts or deployments.
- Public deployments should not accept sensitive or operational utility records. This is not a dispatch, power-grid-control, or emergency-response system.
