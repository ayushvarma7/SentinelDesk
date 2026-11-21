import { useMemo, useState } from 'react'
import { AlertOctagon, ArrowDown, ArrowUp, ChevronsUpDown, RefreshCw, Search, ChevronRight } from 'lucide-react'
import type { Ticket } from '../api'
import { useT, LangContext } from '../i18n'
import { useContext } from 'react'
import { ConfidenceBar, PRIO_STYLE, PriorityBadge, StatusPill, fmtDate } from '../ui'
import TicketDetail from './TicketDetail'

type SortKey = 'id' | 'subject' | 'priority' | 'type' | 'queue' | 'created_at' | 'status' | 'assigned_to' | 'confidence'
const PRIO_RANK = { high: 0, medium: 1, low: 2 } as const
const isHot = (tag: string) => /injection|credential|destructive|^legal$|major-incident/.test(tag)

export default function Tickets({ tickets, reload, onUpdate, loading }: {
  tickets: Ticket[]; reload: () => void; onUpdate: (t: Ticket) => void; loading: boolean
}) {
  const t = useT()
  const { lang } = useContext(LangContext)
  const [q, setQ] = useState('')
  const [prio, setPrio] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useState<{ k: SortKey; dir: 1 | -1 }>({ k: 'created_at', dir: -1 })
  const [openId, setOpenId] = useState<string | null>(null)

  const burst = tickets.filter(x => x.triage.burst?.active)
  const burstGroup = useMemo(() => {
    if (!burst.length) return [] as Ticket[]
    // Active tickets plus the earlier tickets the detector matched them against (burst.related = live ids).
    const ids = new Set<string>()
    burst.forEach(b => { if (b.triage.burst.live_id) ids.add(b.triage.burst.live_id); (b.triage.burst.related ?? []).forEach(r => ids.add(r)) })
    return tickets.filter(x => x.triage.burst?.live_id && ids.has(x.triage.burst.live_id))
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
  }, [tickets, burst])

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const out = tickets.filter(x =>
      (!prio || x.priority === prio) && (!status || x.status === status) &&
      (!needle || [x.id, x.subject, x.summary, x.queue, x.assigned_to, x.requester.name, ...x.tags].join(' ').toLowerCase().includes(needle)))
    const val = (x: Ticket): string | number => sort.k === 'priority' ? PRIO_RANK[x.priority] : (x[sort.k] as string | number)
    return [...out].sort((a, b) => (val(a) < val(b) ? -1 : val(a) > val(b) ? 1 : 0) * sort.dir)
  }, [tickets, q, prio, status, sort])

  const open = tickets.find(x => x.id === openId)
  if (open) return <TicketDetail ticket={open} onBack={() => setOpenId(null)} onUpdate={onUpdate} />

  const Th = ({ k, label, className = '' }: { k: SortKey; label: string; className?: string }) => (
    <th className={`px-3 py-2.5 text-left ${className}`}>
      <button className="inline-flex items-center gap-1 font-semibold hover:text-white" onClick={() => setSort(s => ({ k, dir: s.k === k ? (s.dir === 1 ? -1 : 1) : 1 }))}>
        {label}{sort.k === k ? (sort.dir === 1 ? <ArrowUp size={12} /> : <ArrowDown size={12} />) : <ChevronsUpDown size={12} className="opacity-40" />}
      </button>
    </th>
  )

  return (
    <div className="space-y-4">
      {burstGroup.length > 0 && (
        <div className="flex items-center gap-4 rounded-xl bg-red-600 px-5 py-3.5 text-white shadow-lg shadow-red-600/20">
          <span className="pulse-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/15"><AlertOctagon size={20} /></span>
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{t('majorIncident')}: {burstGroup[0].queue}</div>
            <div className="text-sm text-red-100">{burstGroup.length} {t('majorIncidentSub')}</div>
          </div>
          <div className="hidden flex-wrap gap-1.5 md:flex">
            {burstGroup.map(b => (
              <button key={b.id} onClick={() => setOpenId(b.id)} className="rounded-md bg-white/15 px-2 py-1 font-mono text-xs hover:bg-white/25">{b.id}</button>
            ))}
          </div>
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
            <input value={q} onChange={e => setQ(e.target.value)} placeholder={t('search')}
              className="w-64 rounded-lg border border-slate-300 bg-white py-2 pl-8 pr-3 text-sm outline-none focus:border-navy focus:ring-2 focus:ring-navy/10" />
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

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] text-sm">
            <thead className="bg-navy text-xs uppercase tracking-wide text-slate-300">
              <tr>
                <Th k="id" label={t('id')} className="pl-4" />
                <Th k="subject" label={t('summary')} />
                <Th k="priority" label={t('priority')} />
                <Th k="type" label={t('type')} />
                <Th k="queue" label={t('queue')} />
                <Th k="created_at" label={t('date')} />
                <Th k="status" label={t('status')} />
                <Th k="assigned_to" label={t('assigned')} />
                <th className="px-3 py-2.5 text-left font-semibold">{t('tags')}</th>
                <Th k="confidence" label={t('confidence')} />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/70">
              {rows.map(x => (
                <tr key={x.id} onClick={() => setOpenId(x.id)}
                  className={`cursor-pointer border-l-4 transition-colors ${PRIO_STYLE[x.priority]?.row} ${PRIO_STYLE[x.priority]?.bar}`}>
                  <td className="whitespace-nowrap px-3 py-2.5 pl-4 font-mono text-xs font-semibold text-navy">{x.id}</td>
                  <td className="max-w-[260px] px-3 py-2.5">
                    <div className="truncate font-medium text-slate-900">{x.subject}</div>
                    <div className="truncate text-xs text-slate-500">{x.requester.name} · {x.language.toUpperCase()}</div>
                  </td>
                  <td className="px-3 py-2.5"><PriorityBadge p={x.priority} /></td>
                  <td className="px-3 py-2.5 text-slate-700">{x.type}</td>
                  <td className="max-w-[170px] truncate px-3 py-2.5 text-slate-700" title={x.queue}>{x.queue}</td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-xs text-slate-600">{fmtDate(x.created_at, lang)}</td>
                  <td className="px-3 py-2.5"><StatusPill s={x.status} /></td>
                  <td className="max-w-[150px] truncate px-3 py-2.5 text-slate-700" title={x.assigned_to}>{x.assigned_to}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex max-w-[170px] items-center gap-1 overflow-hidden" title={x.tags.join(', ')}>
                      {[...x.tags].sort((a, b) => Number(isHot(b)) - Number(isHot(a))).slice(0, 2).map(tag => (
                        <span key={tag} className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium ${isHot(tag) ? 'bg-red-600 text-white' : 'bg-white/80 text-slate-600 ring-1 ring-slate-200'}`}>{tag}</span>
                      ))}
                      {x.tags.length > 2 && <span className="text-[10px] text-slate-400">+{x.tags.length - 2}</span>}
                    </div>
                  </td>
                  <td className="px-3 py-2.5"><ConfidenceBar v={x.confidence} /></td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={10} className="px-4 py-10 text-center text-slate-400">{loading ? t('loading') : '—'}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
