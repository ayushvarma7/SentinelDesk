# Handoff: SentinelDesk API for the customer portal

For: the session building `/customer-portal` (separate app on **:5174**).
Owner of the API: `/api` (FastAPI). Don't edit `/api`, `/frontend`, `src/`; ask for changes here instead.

## Run the API

```bash
SD_MOCK=1 .venv/bin/uvicorn api.main:app --port 8000 --reload --reload-dir api
# or ./run_dev.sh  (API :8000 + agent console :5173)
```

- Base URL: `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.
- CORS allows `http://localhost:5174` and `http://127.0.0.1:5174` (plus :5173 for the agent console).
- Storage is **in memory**: restarting the API resets to the 40 seed tickets and ticket numbers start again.
- `GET /health` -> `{"ok": true, "mode": "mock" | "real", "reason": "...", "tickets": 40}`.

## The three endpoints the portal uses

### 1. `POST /tickets` (customer submits a ticket)

Request (`Content-Type: application/json`; every field optional, `null` and `""` are accepted):

```json
{ "subject": "Outlook not syncing", "body": "Outlook stopped syncing my mailbox.",
  "name": "Jane Doe", "email": "jane@example.com", "kind": "incident" }
```

- `kind`: `"incident"` or `"request"` (which card was used). It's stored but **doesn't drive the type**: the
  pipeline predicts `type` (Incident/Request/Problem/Change) from the text.
- Subject and body are truncated server-side to 20,000 characters each. Empty, emoji-only, and very long input
  all return 200 (empty or emoji-only tickets escalate with "Too little text to triage").
- Non-string values (for example `"subject": 123`) return **422**.
- Triage runs synchronously before the response (mock: ~50 ms; real pipeline: up to a few seconds with
  Gemini). There is no polling step: the response is the finished ticket.

Response: **200**, the full ticket record (shape below).

### 2. `GET /tickets?email=<address>` (my tickets)

- Returns an array of tickets whose `requester.email` matches, **case-insensitive**, newest first.
- Unknown email returns `[]`. A missing or empty `email` returns **all** tickets, so always pass it from the portal.
- `?requester=` is an older alias with the same behaviour.
- Seeded addresses that already have history: `h.ortiz@stmarys-health.org`, `r.kim@northpeak.com`,
  `t.wagner@wagner-logistik.de`, `emily.carter@brightwave.io`.

### 3. `GET /tickets/{id}` (ticket detail / status refresh)

- Returns **200** with one ticket, or **404** `{"detail": "ticket INC-99999 not found"}`.
- IDs look like `INC-10041`, `REQ-…`, `PRB-…`, `CHG-…` (prefix follows the predicted type).
- Status changes when an agent acts in the console (approve -> `Closed` with `final_reply` set;
  reject -> `In Progress`). Re-fetch this endpoint to see that; nothing is pushed to clients.

## Ticket record: what to show a customer

| Field | Type | Show to customer? |
|---|---|---|
| `id` | string | yes |
| `subject` | string (`"(no subject)"` if empty) | yes |
| `status` | `"New" \| "In Progress" \| "Auto-Resolved" \| "Escalated" \| "Closed"` | yes |
| `final_reply` | string or `null` | **yes, this is the answer.** Non-null only when the AI auto-resolved the ticket or an agent approved a reply. May contain citation markers like `[TKT-60018]`. |
| `created_at`, `sla_due` | ISO-8601 UTC strings | yes |
| `priority` | `"high" \| "medium" \| "low"` | optional |
| `type`, `queue`, `language` (`"en"`/`"de"`) | string | optional |
| `requester` | `{ "name", "email" }` | yes (their own) |
| `body` | string, **PII-masked** (`<email>`, `<tel_num>`, `<acc_num>`, `<ip_address>`) | prefer showing what they typed locally |
| `summary`, `channel`, `tags`, `confidence`, `escalated`, `assigned_to`, `history` | internal | no |
| `triage`, `agent_trace`, `copilot`, `engine_mode` | internal (model output, escalation reasons, agent-only draft suggestions) | **no** |

Rules of thumb:
- Show an answer only from `final_reply`. **Never** show `copilot.text` or `triage.draft_reply` to a customer:
  `copilot.text` is an internal suggestion that an agent hasn't approved yet.
- `escalated: true` with `final_reply: null` means a human will respond, so show the ticket ID as the reference.
- To show the precedent behind a `[TKT-xxxxx]` chip, the data is in
  `triage.precedents[] = { ticket_id, score, subject, body_snippet, answer, language, queue }`. Fine to show
  `subject` and `answer`; they come from resolved historical tickets.

Trimmed example (`POST /tickets` response):

```json
{
  "id": "INC-10041",
  "subject": "Outlook not syncing",
  "status": "Auto-Resolved",
  "escalated": false,
  "final_reply": "Thanks for the details. In a matching case the local Outlook cache was corrupted; ... [TKT-60018]. ...",
  "priority": "medium", "type": "Incident", "queue": "IT Support", "language": "en",
  "requester": { "name": "Jane Doe", "email": "Jane@Example.com" },
  "created_at": "2026-11-21T18:52:10.123456+00:00",
  "sla_due": "2026-11-22T18:52:10.123456+00:00",
  "triage": { "...": "internal" }, "agent_trace": [], "copilot": {}
}
```

Note: `requester.email` is stored as typed (case preserved); only the filter is case-insensitive.

## Errors

FastAPI's standard shape: `{"detail": "<message>"}` for 404/400, and `{"detail": [ ...validation errors ]}` for 422.
