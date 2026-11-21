# SentinelDesk frontend

Vite + React + TypeScript + Tailwind v4 + recharts + lucide-react. Talks to the FastAPI app in `../api`. This is the agent console only; the customer portal is a separate app in `../customer-portal` (:5174), see `../.shared/HANDOFF.md`.

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
| Organisation › Tickets | Quick-filter chips (Needs me, Auto-handled, Major incident, SLA < 1h), sortable table with sticky header, rows tinted by priority, live SLA pills, hover preview, keyboard nav (`↑`/`↓`, `Enter`, `Esc`, `/` to search). Major-incident banner when the burst detector fired in the last 30 min. |
| Ticket detail | Horizontal agent timeline (PII → Triage → Gate → Retrieve → Grade → Draft → Verify → Resolve) with a log panel. High-priority/escalated tickets get the AI copilot: escalation-reason cards and the draft editor. Others get "Handled by agent" with Override. |
| Draft editor | Grammarly-style checks, computed client-side in `src/components/draftAnalysis.ts`: citations underlined (hover = precedent + similarity), unverified figures squiggled amber, PII tokens as violet chips, `+cite` markers on uncited claims. Suggestions rail with Accept/Dismiss; grounding score; Approve & Send is locked while amber issues are open. |
| Dashboard | KPI tiles, tickets by priority, by queue, auto-resolved vs escalated vs total. |

Grounding score = share of factual sentences that cite a retrieved precedent, minus 15 per open unverified figure
and 25 per citation that was not retrieved.

## Demo buttons (header)

- **Replay agent** re-animates the timeline on the open ticket (or opens the newest auto-resolved one).
- **Simulate outage** posts three VPN tickets (EN, EN, DE) through `POST /tickets`; the third trips the burst
  detector and the red banner appears.

## API endpoints

`GET /health`, `POST /triage`, `GET /tickets[?requester=email]`, `GET /tickets/{id}`, `POST /tickets`,
`POST /tickets/{id}/approve|reject|assign`, `GET /metrics`. Interactive docs: http://localhost:8000/docs.
