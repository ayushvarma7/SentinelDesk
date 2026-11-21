# SentinelDesk frontend

Vite + React + TypeScript + Tailwind v4 + recharts + lucide-react. Talks to the FastAPI app in `../api`.

## Run

From the repo root:

```bash
./run_dev.sh                 # API on :8000 (SD_MOCK=1) + UI on :5173
```

Or separately:

```bash
SD_MOCK=1 .venv/bin/uvicorn api.main:app --port 8000 --reload --reload-dir api
cd frontend && npm install && npm run dev
```

`VITE_API_URL` overrides the API base (default `http://localhost:8000`).

## Screens

| Screen | What it shows |
|---|---|
| Organisation › Tickets | Sortable/filterable table, rows tinted by priority, major-incident banner when the burst detector fires. Click a row: high-priority or escalated tickets open the AI copilot card (reasons, cited `[TKT-xxxxx]` chips, unverified-claim warnings, Approve & Send / Edit / Assign / Reject); others open the animated agent-trace stepper with an Override button. |
| Customer Portal | Fake login (any email/phone; `h.ortiz@stmarys-health.org` has seeded history), Raise Incident / Raise Request forms, ticket history, floating assistant that shows the drafted reply. |
| Dashboard | KPI tiles, tickets by priority (donut), by queue, auto-resolved vs escalated vs total. Recall KPI comes from `reports/triage_metrics.json`. |

EN/DE toggle in the top bar switches UI labels. The amber **MOCK** badge means the API is serving mock triage.

## API endpoints

`GET /health`, `POST /triage`, `GET /tickets[?requester=email]`, `GET /tickets/{id}`, `POST /tickets`,
`POST /tickets/{id}/approve|reject|assign`, `GET /metrics`. Interactive docs: http://localhost:8000/docs.
