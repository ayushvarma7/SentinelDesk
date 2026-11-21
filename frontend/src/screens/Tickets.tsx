import { useContext, useEffect, useMemo, useRef, useState } from 'react'
import { AlertOctagon, ArrowDown, ArrowUp, ChevronRight, ChevronsUpDown, Inbox, RefreshCw, Search, ShieldAlert, X } from 'lucide-react'
import type { Ticket } from '../api'
import { LangContext, useT } from '../i18n'
import { ConfidenceBar, PRIO_STYLE, PriorityBadge, Skeleton, SlaPill, StatusPill, fmtDate, slaMinutesLeft, useNow } from '../ui'
import TicketDetail from './TicketDetail'

type SortKey = 'id' | 'subject' | 'priority' | 'type' | 'queue' | 'created_at' | 'sla_due' | 'status' | 'assigned_to' | 'confidence'
type Quick = 'all' | 'needsMe' | 'auto' | 'major' | 'sla'
const PRIO_RANK = { high: 0, medium: 1, low: 2 } as const
const DONE = ['Closed', 'Auto-Resolved']
const isHot = (tag: string) => /injection|credential|destructive|^legal$|major-incident/.test(tag)

/** Burst groups: each active ticket plus the earlier tickets the detector matched it against. */
export function burstGroups(tickets: Ticket[]) {
  const byLive = new Map(tickets.filter(t => t.triage.burst?.live_id).map(t => [t.triage.burst.live_id!, t]))
  return tickets.filter(t => t.triage.burst?.active).map(a => {
    const members = [a, ...(a.triage.burst.related ?? []).map(id => byLive.get(id)).filter((x): x is Ticket => !!x)]
    return { key: a.id, at: a.created_at, members: members.sort((x, y) => x.created_at.localeCompare(y.created_at)) }
  }).sort((x, y) => y.at.localeCompare(x.at))
}

export default function Tickets({ tickets, reload, onUpdate, loading, openId, setOpenId, replay }: {
  tickets: Ticket[]; reload: () => void; onUpdate: (t: Ticket) => void; loading: boolean
  openId: string | null; setOpenId: (id: string | null) => void; replay: number
}) {
  const t = useT()
  const { lang } = useContext(LangContext)
  const now = useNow(1000)
  const [q, setQ] = useState('')
  const [prio, setPrio] = useState('')
  const [status, setStatus] = useState('')
  const [quick, setQuick] = useState<Quick>('all')
  const [sort, setSort] = useState<{ k: SortKey; dir: 1 | -1 }>({ k: 'created_at', dir: -1 })
  const [sel, setSel] = useState(0)
  const [ack, setAck] = useState<Set<string>>(new Set())
  const [preview, setPreview] = useState<{ id: string; left: number; top: number; above: boolean } | null>(null)
  const hoverTimer = useRef<number | undefined>(undefined)
  const rowRefs = useRef<Map<string, HTMLTableRowElement>>(new Map())
  const searchRef = useRef<HTMLInputElement>(null)

  const groups = useMemo(() => burstGroups(tickets), [tickets])
  const majorIds = useMemo(() => new Set(groups.flatMap(g => g.members.map(m => m.id))), [groups])
  // Banner: newest burst inside the 30-minute window that hasn't been acknowledged.
  const banner = groups.find(g => now - new Date(g.at).getTime() < 30 * 60e3 && !ack.has(g.key))

  const quickTest: Record<Quick, (x: Ticket) => boolean> = {
    all: () => true,
    needsMe: x => (x.escalated || x.priority === 'high') && !DONE.includes(x.status),
    auto: x => x.status === 'Auto-Resolved',
    major: x => majorIds.has(x.id),
    sla: x => !DONE.includes(x.status) && slaMinutesLeft(x.sla_due, now) < 60,
  }
  const counts = Object.fromEntries((Object.keys(quickTest) as Quick[]).map(k => [k, tickets.filter(quickTest[k]).length])) as Record<Quick, number>

  const slaTick = quick === 'sla' ? now : 0   // only the SLA chip depends on the clock
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const out = tickets.filter(x => quickTest[quick](x) &&
      (!prio || x.priority === prio) && (!status || x.status === status) &&
      (!needle || [x.id, x.subject, x.summary, x.queue, x.assigned_to, x.requester.name, ...x.tags].join(' ').toLowerCase().includes(needle)))
    const val = (x: Ticket): string | number => sort.k === 'priority' ? PRIO_RANK[x.priority] : (x[sort.k] as string | number)
    return [...out].sort((a, b) => (val(a) < val(b) ? -1 : val(a) > val(b) ? 1 : 0) * sort.dir)
  }, [tickets, q, prio, status, quick, sort, majorIds, slaTick]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setSel(s => Math.min(s, Math.max(0, rows.length - 1))) }, [rows.length])

  const showPreview = (id: string, el: HTMLElement) => {
    const r = el.getBoundingClientRect()
    const above = r.bottom + 150 > window.innerHeight
    setPreview({ id, left: Math.min(r.left + 120, window.innerWidth - 400), top: above ? r.top - 6 : r.bottom + 6, above })
  }

  // Keyboard: ↑/↓ move, Enter opens, / focuses search. Esc (back) is handled in App.
  useEffect(() => {
    if (openId) return
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') { if (e.key === 'Escape') (e.target as HTMLElement).blur(); return }
      if (e.key === '/') { e.preventDefault(); searchRef.current?.focus(); return }
      if (!rows.length) return
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const n = Math.max(0, Math.min(rows.length - 1, sel + (e.key === 'ArrowDown' ? 1 : -1)))
        setSel(n)
        const el = rowRefs.current.get(rows[n].id)
        if (el) { el.scrollIntoView({ block: 'nearest' }); showPreview(rows[n].id, el) }
      } else if (e.key === 'Enter') { setPreview(null); setOpenId(rows[sel]?.id ?? null) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [rows, sel, openId, setOpenId])

  const open = tickets.find(x => x.id === openId)
  if (open) return <TicketDetail ticket={open} onBack={() => setOpenId(null)} onUpdate={onUpdate} replay={replay} />

  const Th = ({ k, label, className = '' }: { k: SortKey; label: string; className?: string }) => (
    <th className={`sticky top-0 z-10 bg-navy px-2.5 py-2.5 text-left ${className}`}>
      <button className="inline-flex items-center gap-1 font-semibold hover:text-white" onClick={() => setSort(s => ({ k, dir: s.k === k ? (s.dir === 1 ? -1 : 1) : 1 }))}>
        {label}{sort.k === k ? (sort.dir === 1 ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ChevronsUpDown size={12} className="opacity-40" />}
      </button>
    </th>
  )
  const chips: [Quick, string, string][] = [
    ['all', t('qAll'), 'bg-slate-500'], ['needsMe', t('qNeedsMe'), 'bg-coral'], ['auto', t('qAuto'), 'bg-teal-500'],
    ['major', t('qMajor'), 'bg-red-600'], ['sla', t('qSla'), 'bg-amber-400'],
  ]
  const pv = preview && tickets.find(x => x.id === preview.id)
  const clearAll = () => { setQ(''); setPrio(''); setStatus(''); setQuick('all') }

  return (
    <div className="space-y-4">
      {banner && (
        <div className="banner-in flex items-center gap-4 rounded-xl bg-red-600 px-5 py-3.5 text-white shadow-lg shadow-red-600/20">
          <span className="pulse-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/15"><AlertOctagon size={20} /></span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{t('majorIncident')}: {banner.members[banner.members.length - 1].queue}</div>
            <div className="text-sm text-red-100">{banner.members.length} {t('majorIncidentSub')}</div>
          </div>
          <div className="hidden flex-wrap gap-1.5 lg:flex">
            {banner.members.slice(-4).map(b => (
              <button key={b.id} onClick={() => setOpenId(b.id)} className="rounded-md bg-white/15 px-2 py-1 font-mono text-xs hover:bg-white/25">{b.id}</button>
            ))}
          </div>
          <button onClick={() => setQuick('major')} className="rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50">View all</button>
          <button onClick={() => setAck(a => new Set(a).add(banner.key))} className="rounded-md p-1 text-red-100 hover:bg-white/15" aria-label="acknowledge" title="Acknowledge"><X size={16} /></button>
        </div>
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-medium text-slate-500">{t('organisation')} <ChevronRight size={12} className="inline" /> {t('tickets')}</div>
          <h1 className="text-2xl font-bold text-navy">{t('tickets')} <span className="ml-1 text-base font-medium text-slate-400">{rows.length} {t('results')}</span></h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input ref={searchRef} value={q} onChange={e => setQ(e.target.value)} placeholder={t('search')}
              className="w-60 rounded-lg border border-slate-300 bg-white py-2 pl-8 pr-8 text-sm outline-none focus:border-navy focus:ring-2 focus:ring-navy/10" />
            <kbd className="absolute right-2 top-1/2 -translate-y-1/2 rounded border border-slate-200 px-1 font-mono text-[10px] text-slate-400">/</kbd>
          </div>
          <select value={prio} onChange={e => setPrio(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm">
            <option value="">{t('allPriorities')}</option>
            <option value="high">{t('high')}</option><option value="medium">{t('medium')}</option><option value="low">{t('low')}</option>
          </select>
          <select value={status} onChange={e => setStatus(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm">
            <option value="">{t('allStatuses')}</option>
            {['New', 'In Progress', 'Auto-Resolved', 'Escalated', 'Closed'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={reload} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm hover:bg-slate-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />{t('refresh')}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {chips.map(([k, label, dot]) => (
          <button key={k} onClick={() => setQuick(k)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition ${quick === k ? 'border-navy bg-navy text-white shadow-sm' : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'}`}>
            <span className={`h-2 w-2 rounded-full ${dot}`} />{label}
            <span className={`rounded-full px-1.5 text-xs tabular-nums ${quick === k ? 'bg-white/20' : 'bg-slate-100 text-slate-600'}`}>{counts[k]}</span>
          </button>
        ))}
        <span className="ml-auto hidden text-xs text-slate-400 xl:inline">
          <kbd className="rounded border border-slate-300 bg-white px-1 font-mono">↑</kbd> <kbd className="rounded border border-slate-300 bg-white px-1 font-mono">↓</kbd> move · <kbd className="rounded border border-slate-300 bg-white px-1 font-mono">Enter</kbd> open · <kbd className="rounded border border-slate-300 bg-white px-1 font-mono">Esc</kbd> back
        </span>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="max-h-[calc(100vh-310px)] min-h-[320px] overflow-auto" onScroll={() => setPreview(null)}>
          <table className="w-full min-w-[1080px] text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-slate-300">
              <tr>
                <Th k="id" label={t('id')} className="pl-4" />
                <Th k="subject" label={t('summary')} />
                <Th k="priority" label={t('priority')} />
                <Th k="type" label={t('type')} className="hidden min-[1360px]:table-cell" />
                <Th k="queue" label={t('queue')} />
                <Th k="created_at" label={t('date')} />
                <Th k="sla_due" label="SLA" />
                <Th k="status" label={t('status')} />
                <Th k="assigned_to" label={t('assigned')} />
                <th className="sticky top-0 z-10 bg-navy px-2.5 py-2.5 text-left font-semibold">{t('tags')}</th>
                <Th k="confidence" label={t('confidence')} className="pr-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/70">
              {loading && tickets.length === 0 && Array.from({ length: 9 }).map((_, i) => (
                <tr key={`sk${i}`} className="border-l-4 border-l-slate-200">
                  {[70, 200, 60, 120, 80, 60, 80, 110, 90, 70].map((w, k) => (
                    <td key={k} className="px-2.5 py-3.5"><Skeleton className="h-3.5" /><div style={{ width: w }} /></td>
                  ))}
                </tr>
              ))}
              {rows.map((x, i) => (
                <tr key={x.id} ref={el => { if (el) rowRefs.current.set(x.id, el); else rowRefs.current.delete(x.id) }}
                  onClick={() => { setPreview(null); setOpenId(x.id) }}
                  onMouseEnter={e => { setSel(i); const el = e.currentTarget; clearTimeout(hoverTimer.current); hoverTimer.current = window.setTimeout(() => showPreview(x.id, el), 280) }}
                  onMouseLeave={() => { clearTimeout(hoverTimer.current); setPreview(null) }}
                  className={`cursor-pointer border-l-4 transition-colors ${PRIO_STYLE[x.priority]?.row} ${PRIO_STYLE[x.priority]?.bar} ${i === sel ? 'outline-2 -outline-offset-2 outline-navy/50' : ''}`}>
                  <td className="whitespace-nowrap px-2.5 py-2.5 pl-4 font-mono text-xs font-semibold text-navy">{x.id}</td>
                  <td className="max-w-[200px] px-2.5 py-2.5 min-[1360px]:max-w-[240px]">
                    <div className="truncate font-medium text-slate-900">{x.subject}</div>
                    <div className="truncate text-xs text-slate-500">{x.requester.name} · {x.language.toUpperCase()}<span className="min-[1360px]:hidden"> · {x.type}</span></div>
                  </td>
                  <td className="px-2.5 py-2.5"><PriorityBadge p={x.priority} /></td>
                  <td className="hidden px-2.5 py-2.5 text-xs text-slate-700 min-[1360px]:table-cell">{x.type}</td>
                  <td className="max-w-[135px] truncate px-2.5 py-2.5 text-slate-700 min-[1360px]:max-w-[160px]" title={x.queue}>{x.queue}</td>
                  <td className="whitespace-nowrap px-2.5 py-2.5 text-xs text-slate-600">{fmtDate(x.created_at, lang)}</td>
                  <td className="px-2.5 py-2.5"><SlaPill due={x.sla_due} done={DONE.includes(x.status)} now={now} /></td>
                  <td className="px-2.5 py-2.5"><StatusPill s={x.status} /></td>
                  <td className="max-w-[115px] truncate px-2.5 py-2.5 text-slate-700 min-[1360px]:max-w-[140px]" title={x.assigned_to}>{x.assigned_to}</td>
                  <td className="px-2.5 py-2.5">
                    <div className="flex max-w-[110px] items-center gap-1 overflow-hidden min-[1360px]:max-w-[150px]" title={x.tags.join(', ')}>
                      {[...x.tags].sort((a, b) => Number(isHot(b)) - Number(isHot(a))).slice(0, 2).map(tag => (
                        <span key={tag} className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium ${isHot(tag) ? 'bg-red-600 text-white' : 'bg-white/80 text-slate-600 ring-1 ring-slate-200'}`}>{tag}</span>
                      ))}
                      {x.tags.length > 2 && <span className="text-[10px] text-slate-400">+{x.tags.length - 2}</span>}
                    </div>
                  </td>
                  <td className="px-2.5 py-2.5 pr-4"><ConfidenceBar v={x.confidence} /></td>
                </tr>
              ))}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={11}>
                  <div className="flex flex-col items-center gap-2 py-14 text-center">
                    <span className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400"><Inbox size={24} /></span>
                    <div className="font-semibold text-slate-700">{tickets.length ? 'No tickets match these filters' : 'No tickets yet'}</div>
                    <div className="text-sm text-slate-500">{tickets.length ? 'Try another quick filter or clear the search.' : 'New tickets from the customer portal appear here.'}</div>
                    {tickets.length > 0 && <button onClick={clearAll} className="mt-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50">Clear filters</button>}
                  </div>
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {pv && preview && (
        <div className="pointer-events-none fixed z-40 w-[380px] rounded-xl bg-white p-4 shadow-2xl ring-1 ring-slate-200"
          style={{ left: preview.left, top: preview.top, transform: preview.above ? 'translateY(-100%)' : undefined }}>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-coral">{pv.id}</span>
            <PriorityBadge p={pv.priority} /><StatusPill s={pv.status} />
          </div>
          <p className="mt-2 line-clamp-3 text-sm leading-snug text-slate-700">{pv.summary}</p>
          {pv.triage.escalation_reasons[0] ? (
            <div className="mt-2.5 flex items-start gap-2 rounded-lg bg-red-50 px-2.5 py-2 text-xs text-red-800">
              <ShieldAlert size={14} className="mt-px shrink-0" />
              <span>{pv.triage.escalation_reasons[0]}{pv.triage.escalation_reasons.length > 1 && <b> · +{pv.triage.escalation_reasons.length - 1} more</b>}</span>
            </div>
          ) : <div className="mt-2.5 rounded-lg bg-teal-50 px-2.5 py-2 text-xs text-teal-800">Auto-handled: grounded reply sent with {pv.triage.cited_ticket_ids.length} citation(s)</div>}
          <div className="mt-2 text-[11px] text-slate-400">Enter or click to open</div>
        </div>
      )}
    </div>
  )
}
