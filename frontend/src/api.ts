// Types mirror src/sentineldesk/schema.py (TriageResult) and api/main.py (ticket record).

export const API_BASE: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Priority = 'high' | 'medium' | 'low'
export type Status = 'New' | 'In Progress' | 'Auto-Resolved' | 'Escalated' | 'Closed'

export interface Prediction { label: string; confidence: number; all_probs: Record<string, number> }

export interface Precedent {
  ticket_id: string; score: number; subject: string; body_snippet: string
  answer: string; language: string; queue: string
}

export interface TriageResult {
  language: string
  type: Prediction; queue: Prediction; priority: Prediction
  escalate: boolean; escalation_reasons: string[]
  precedents: Precedent[]
  draft_reply: string | null; cited_ticket_ids: string[]; unverified_claims: string[]
  masked_pii: Record<string, number>; latency_ms: Record<string, number>
  risks: string[]
  burst: { active?: boolean; related?: string[]; live_id?: string | null; max_sim?: number }
  engine: string | null
  overall_confidence: number
}

export type PhaseStatus = 'done' | 'warning' | 'skipped' | 'escalated' | 'failed'
export interface Phase { phase: string; status: PhaseStatus; duration_ms: number; logs: string[] }

export interface Ticket {
  id: string; subject: string; body: string; summary: string
  requester: { name: string; email: string }
  channel: string; created_at: string; sla_due: string
  status: Status; assigned_to: string; tags: string[]
  priority: Priority; type: string; queue: string; language: string
  confidence: number; escalated: boolean; engine_mode: string
  triage: TriageResult; agent_trace: Phase[]
  copilot: { text: string | null; cited_ids: string[]; unverified: string[]; source: string }
  final_reply: string | null
  history: { at: string; actor: string; action: string }[]
}

export interface Metrics {
  mode: string; total: number; auto_resolved: number; escalated: number
  escalation_rate: number; avg_latency_ms: number
  by_priority: Record<string, number>; by_queue: Record<string, number>; by_status: Record<string, number>
  kpi: { high_priority_incident_recall: number | null; high_incident_escalated: number | null; auto_share_validation: number | null }
  major_incident: { active: boolean; ticket_ids: string[] }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try { const j = await res.json(); if (j?.detail) msg = String(j.detail) } catch { /* not json */ }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => req<{ ok: boolean; mode: string; reason: string; tickets: number }>('/health'),
  tickets: (requester?: string) =>
    req<Ticket[]>('/tickets' + (requester ? `?requester=${encodeURIComponent(requester)}` : '')),
  ticket: (id: string) => req<Ticket>(`/tickets/${encodeURIComponent(id)}`),
  create: (b: { subject: string; body: string; name: string; email: string; kind: string }) =>
    req<Ticket>('/tickets', { method: 'POST', body: JSON.stringify(b) }),
  approve: (id: string, reply?: string) =>
    req<Ticket>(`/tickets/${id}/approve`, { method: 'POST', body: JSON.stringify({ agent: 'You', reply: reply ?? null }) }),
  reject: (id: string, reason?: string) =>
    req<Ticket>(`/tickets/${id}/reject`, { method: 'POST', body: JSON.stringify({ agent: 'You', reason: reason ?? null }) }),
  assign: (id: string) =>
    req<Ticket>(`/tickets/${id}/assign`, { method: 'POST', body: JSON.stringify({ agent: 'You' }) }),
  metrics: () => req<Metrics>('/metrics'),
  triage: (subject: string, body: string) =>
    req<TriageResult & { mode: string }>('/triage', { method: 'POST', body: JSON.stringify({ subject, body }) }),
}
