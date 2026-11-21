import { useContext, useEffect, useState } from 'react'
import {
  AlertTriangle, ArrowLeft, Bot, Check, CheckCircle2, ChevronDown, CircleDashed, Clock, Edit3, Loader2,
  ShieldAlert, ShieldCheck, Send, Sparkles, UserCheck, UserRound, XCircle, MinusCircle, Languages, Lock,
} from 'lucide-react'
import { api, type Phase, type Precedent, type Ticket } from '../api'
import { LangContext, useT } from '../i18n'
import { Card, CitedText, PrecedentModal, PriorityBadge, SlaCountdown, StatusPill, fmtDate } from '../ui'

const DONE = ['Closed', 'Auto-Resolved']

export default function TicketDetail({ ticket, onBack, onUpdate }: { ticket: Ticket; onBack: () => void; onUpdate: (t: Ticket) => void }) {
  const t = useT()
  const [override, setOverride] = useState(false)
  const [prec, setPrec] = useState<Precedent | null>(null)
  const copilotView = ticket.escalated || ticket.priority === 'high' || override

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-navy">
        <ArrowLeft size={15} />{t('back')}
      </button>
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-sm font-semibold text-coral">{ticket.id}</span>
        <h1 className="text-xl font-bold text-navy">{ticket.subject}</h1>
        <PriorityBadge p={ticket.priority} /><StatusPill s={ticket.status} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-4">
          {copilotView
            ? <CopilotCard ticket={ticket} onUpdate={onUpdate} openPrec={setPrec} />
            : <AgentView ticket={ticket} openPrec={setPrec} onOverride={async () => { onUpdate(await api.reject(ticket.id, 'Override')); setOverride(true) }} />}
          <Card className="p-5">
            <SectionTitle>{t('ticketBody')}</SectionTitle>
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-700">{ticket.body || '—'}</p>
          </Card>
          {copilotView && <TraceCard phases={ticket.agent_trace} animate={false} />}
        </div>
        <SideForm ticket={ticket} />
      </div>
      <PrecedentModal p={prec} onClose={() => setPrec(null)} />
    </div>
  )
}

function SectionTitle({ children, icon }: { children: React.ReactNode; icon?: React.ReactNode }) {
  return <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">{icon}{children}</div>
}

function PiiChip({ ticket }: { ticket: Ticket }) {
  const t = useT()
  const pii = ticket.triage.masked_pii || {}
  const n = Object.values(pii).reduce((a, b) => a + b, 0)
  if (!n) return null
  return (
    <span title={Object.entries(pii).map(([k, v]) => `${k}: ${v}`).join(', ')}
      className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">
      <Lock size={11} />{t('piiMasked')} · {n}
    </span>
  )
}

/* ---------------------------------------------------------------- high priority / escalated */
function CopilotCard({ ticket, onUpdate, openPrec }: { ticket: Ticket; onUpdate: (t: Ticket) => void; openPrec: (p: Precedent) => void }) {
  const t = useT()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(ticket.copilot.text ?? '')
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setDraft(ticket.copilot.text ?? '') }, [ticket.id, ticket.copilot.text])

  const act = async (name: string, fn: () => Promise<Ticket>) => {
    setBusy(name); setErr(null)
    try { onUpdate(await fn()); setEditing(false) } catch (e) { setErr(String((e as Error).message)) } finally { setBusy(null) }
  }
  const closed = ticket.status === 'Closed'
  const high = ticket.priority === 'high'
  const r = ticket.triage

  return (
    <Card className={`overflow-hidden ${high ? 'ring-2 ring-coral/60' : ''}`}>
      <div className={`flex flex-wrap items-center justify-between gap-3 px-5 py-3 ${high ? 'bg-navy text-white' : 'bg-slate-800 text-white'}`}>
        <div className="flex items-center gap-2.5">
          <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${high ? 'bg-coral pulse-ring' : 'bg-white/15'}`}><Sparkles size={16} /></span>
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-300">AI Copilot</div>
            <div className="font-semibold">{high ? t('needsYou') : t('needsReview')}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-white/10 px-3 py-1.5">
          <Clock size={14} className="text-slate-300" /><span className="text-xs text-slate-300">{t('sla')}</span>
          <span className="[&_span]:!text-white"><SlaCountdown due={ticket.sla_due} done={DONE.includes(ticket.status)} /></span>
        </div>
      </div>

      <div className="space-y-5 p-5">
        <div>
          <p className="line-clamp-2 text-[15px] font-medium leading-snug text-slate-900">{ticket.summary}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-slate-600">
            <span className="inline-flex items-center gap-1"><UserRound size={14} />{t('raisedBy')}: <b className="font-medium text-slate-800">{ticket.requester.name}</b></span>
            <span className="inline-flex items-center gap-1"><Languages size={14} />{t('language')}: <b className="font-medium uppercase text-slate-800">{ticket.language}</b></span>
            <PiiChip ticket={ticket} />
          </div>
        </div>

        {r.escalation_reasons.length > 0 && (
          <div>
            <SectionTitle icon={<ShieldAlert size={13} />}>{t('escalationReasons')}</SectionTitle>
            <div className="flex flex-wrap gap-2">
              {r.escalation_reasons.map(x => {
                const hard = /injection|credential|destructive|Legal|Security|major incident|Critical/i.test(x)
                return <span key={x} className={`rounded-md px-2.5 py-1 text-xs font-medium ${hard ? 'bg-red-100 text-red-800 ring-1 ring-red-200' : 'bg-slate-100 text-slate-700 ring-1 ring-slate-200'}`}>{x}</span>
              })}
            </div>
          </div>
        )}

        <div>
          <SectionTitle icon={<Bot size={13} />}>{closed ? t('finalReply') : t('recommended')}</SectionTitle>
          {closed && ticket.final_reply ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm">
              <CitedText text={ticket.final_reply} precedents={r.precedents} onOpen={openPrec} />
            </div>
          ) : editing ? (
            <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={6}
              className="w-full rounded-lg border border-navy/30 p-3 text-sm outline-none focus:ring-2 focus:ring-navy/15" />
          ) : ticket.copilot.text ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
              <CitedText text={draft || ticket.copilot.text} precedents={r.precedents} onOpen={openPrec} />
            </div>
          ) : <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">{t('noDraft')}</div>}

          {ticket.copilot.unverified.length > 0 && !closed && (
            <div className="mt-2 space-y-1.5">
              {ticket.copilot.unverified.map(u => (
                <div key={u} className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  <AlertTriangle size={14} className="mt-px shrink-0 text-amber-500" />
                  <span><b>{t('unverified')}:</b> “{u}” is not supported by any retrieved precedent.</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {!closed && (
          <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
            <button disabled={!!busy || !draft.trim()} onClick={() => act('approve', () => api.approve(ticket.id, draft !== ticket.copilot.text ? draft : undefined))}
              className="inline-flex items-center gap-1.5 rounded-lg bg-coral px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-coral-dark disabled:opacity-50">
              {busy === 'approve' ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}{t('approve')}
            </button>
            <button onClick={() => setEditing(e => !e)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50">
              {editing ? <Check size={15} /> : <Edit3 size={15} />}{editing ? t('save') : t('edit')}
            </button>
            <button disabled={!!busy} onClick={() => act('assign', () => api.assign(ticket.id))}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50">
              <UserCheck size={15} />{t('assignMe')}
            </button>
            <button disabled={!!busy} onClick={() => act('reject', () => api.reject(ticket.id))}
              className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50">
              <XCircle size={15} />{t('reject')}
            </button>
          </div>
        )}
        {err && <div className="text-sm text-red-600">{err}</div>}
        <PrecedentList precs={r.precedents} cited={ticket.copilot.cited_ids} openPrec={openPrec} />
      </div>
    </Card>
  )
}

function PrecedentList({ precs, cited, openPrec }: { precs: Precedent[]; cited: string[]; openPrec: (p: Precedent) => void }) {
  const t = useT()
  if (!precs.length) return null
  return (
    <div>
      <SectionTitle>{t('precedents')}</SectionTitle>
      <div className="grid gap-2 sm:grid-cols-3">
        {precs.slice(0, 3).map(p => (
          <button key={p.ticket_id} onClick={() => openPrec(p)}
            className={`rounded-lg border p-3 text-left text-xs hover:border-navy/40 hover:bg-slate-50 ${cited.includes(p.ticket_id) ? 'border-navy/30 bg-navy/[0.03]' : 'border-slate-200'}`}>
            <div className="flex items-center justify-between font-mono font-semibold text-navy"><span>{p.ticket_id}</span><span className="text-slate-500">{p.score.toFixed(3)}</span></div>
            <div className="mt-1 line-clamp-2 text-slate-700">{p.subject}</div>
            <div className="mt-1 text-[10px] uppercase text-slate-400">{p.language} · {p.queue}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- handled by agent */
function AgentView({ ticket, openPrec, onOverride }: { ticket: Ticket; openPrec: (p: Precedent) => void; onOverride: () => void }) {
  const t = useT()
  const reply = ticket.final_reply ?? ticket.triage.draft_reply
  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-teal-50 px-5 py-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-600 text-white"><ShieldCheck size={16} /></span>
            <div>
              <div className="font-semibold text-teal-900">{t('handledByAgent')}</div>
              <div className="text-xs text-teal-700">{ticket.triage.engine ?? '—'} · {ticket.triage.latency_ms.total?.toFixed(0)} ms · <PiiChip ticket={ticket} /></div>
            </div>
          </div>
          <button onClick={onOverride} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50">
            <Edit3 size={14} />{t('override')}
          </button>
        </div>
        <TraceBody phases={ticket.agent_trace} animate />
      </Card>
      {reply && (
        <Card className="p-5">
          <SectionTitle icon={<Send size={13} />}>{ticket.final_reply ? t('finalReply') : t('draftReply')}</SectionTitle>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
            <CitedText text={reply} precedents={ticket.triage.precedents} onOpen={openPrec} />
          </div>
          {ticket.triage.unverified_claims.map(u => (
            <div key={u} className="mt-2 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <AlertTriangle size={14} className="mt-px shrink-0 text-amber-500" /><span><b>{t('unverified')}:</b> “{u}”</span>
            </div>
          ))}
          <div className="mt-4"><PrecedentList precs={ticket.triage.precedents} cited={ticket.triage.cited_ticket_ids} openPrec={openPrec} /></div>
        </Card>
      )}
    </>
  )
}

function TraceCard({ phases, animate }: { phases: Phase[]; animate: boolean }) {
  const t = useT()
  return <Card><div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-navy">{t('agentTrace')}</div><TraceBody phases={phases} animate={animate} /></Card>
}

const PHASE_ICON = {
  done: <CheckCircle2 size={18} className="text-teal-600" />,
  warning: <AlertTriangle size={18} className="text-amber-500" />,
  skipped: <MinusCircle size={18} className="text-slate-300" />,
  escalated: <ShieldAlert size={18} className="text-coral" />,
  failed: <XCircle size={18} className="text-red-600" />,
}

function TraceBody({ phases, animate }: { phases: Phase[]; animate: boolean }) {
  const [shown, setShown] = useState(animate ? 0 : phases.length)
  const [open, setOpen] = useState<Record<number, boolean>>({})
  useEffect(() => {
    if (!animate) { setShown(phases.length); return }
    setShown(0)
    const id = setInterval(() => setShown(s => { if (s >= phases.length) { clearInterval(id); return s } return s + 1 }), 380)
    return () => clearInterval(id)
  }, [phases, animate])

  return (
    <ol className="px-5 py-4">
      {phases.map((p, i) => {
        const visible = i < shown
        const running = i === shown && animate
        if (!visible && !running) return (
          <li key={p.phase} className="flex gap-3 pb-3 opacity-40"><CircleDashed size={18} className="text-slate-300" /><span className="text-sm text-slate-400">{p.phase}</span></li>
        )
        return (
          <li key={p.phase} className={`relative flex gap-3 pb-3 ${visible ? 'step-in' : ''}`}>
            {i < phases.length - 1 && <span className="absolute left-[8.5px] top-6 h-[calc(100%-18px)] w-px bg-slate-200" />}
            <span className="relative z-10 bg-white">{running ? <Loader2 size={18} className="animate-spin text-navy" /> : PHASE_ICON[p.status] ?? PHASE_ICON.done}</span>
            <div className="min-w-0 flex-1">
              <button className="flex w-full items-center justify-between gap-2 text-left" onClick={() => setOpen(o => ({ ...o, [i]: !o[i] }))} disabled={running}>
                <span className={`text-sm font-medium ${p.status === 'skipped' ? 'text-slate-400' : 'text-slate-800'}`}>{p.phase}</span>
                <span className="flex items-center gap-2 text-xs text-slate-400">
                  {!running && <span className="font-mono tabular-nums">{p.duration_ms.toFixed(1)} ms</span>}
                  <ChevronDown size={14} className={`transition-transform ${open[i] ? 'rotate-180' : ''}`} />
                </span>
              </button>
              {!running && <div className="truncate text-xs text-slate-500">{p.logs[0]}</div>}
              {open[i] && !running && (
                <pre className="mt-1.5 overflow-x-auto rounded-md bg-navy px-3 py-2 font-mono text-[11px] leading-relaxed text-slate-200">{p.logs.map(l => `› ${l}`).join('\n')}</pre>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

/* ---------------------------------------------------------------- side form */
function SideForm({ ticket }: { ticket: Ticket }) {
  const t = useT()
  const { lang } = useContext(LangContext)
  const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800">{children}</div>
    </label>
  )
  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-4">
        <div className="text-sm font-semibold text-navy">{t('details')}</div>
        <Row label={t('incId')}><span className="font-mono">{ticket.id}</span></Row>
        <Row label={t('name')}>{ticket.requester.name}<div className="truncate text-xs text-slate-500">{ticket.requester.email}</div></Row>
        <Row label={t('state')}><StatusPill s={ticket.status} /></Row>
        <Row label={t('priority')}><PriorityBadge p={ticket.priority} /> <span className="ml-1 text-xs text-slate-500">{(ticket.triage.priority.confidence * 100).toFixed(0)}%</span></Row>
        <Row label={t('sla')}><SlaCountdown due={ticket.sla_due} done={DONE.includes(ticket.status)} /></Row>
        <div className="grid grid-cols-2 gap-3">
          <Row label={t('type')}>{ticket.type}</Row>
          <Row label={t('language')}><span className="uppercase">{ticket.language}</span></Row>
        </div>
        <Row label={t('queue')}>{ticket.queue}</Row>
        <Row label={t('assigned')}>{ticket.assigned_to}</Row>
        <Row label={t('created')}>{fmtDate(ticket.created_at, lang)} · {ticket.channel}</Row>
      </Card>
      <Card className="p-4">
        <div className="mb-2 text-sm font-semibold text-navy">{t('history')}</div>
        <ol className="space-y-2 text-xs">
          {[...ticket.history].reverse().map((h, i) => (
            <li key={i} className="border-l-2 border-slate-200 pl-2.5">
              <div className="font-medium text-slate-800">{h.action}</div>
              <div className="text-slate-500">{h.actor} · {fmtDate(h.at, lang)}</div>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}
