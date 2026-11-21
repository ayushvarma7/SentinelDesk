// Problem database screen (src/sentineldesk/store.py via api/main.py): search, every distinct problem,
// a problem's attached tickets, resolve / reopen, and the triage log.
import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Loader2, RotateCcw, Search } from 'lucide-react'
import { api, type DbStats, type LogRow, type ProblemDetail, type ProblemRow } from '../api'
import { useToast } from '../toast'
import { Card } from '../ui'
import { MetricCard, PageHeader } from '../components/kit'

type Tab = 'problems' | 'search' | 'log'
type SearchHit = Awaited<ReturnType<typeof api.searchProblems>>

export default function Problems({ openId, setOpenId }: { openId: number | null; setOpenId: (id: number | null) => void }) {
  const toast = useToast()
  const [tab, setTab] = useState<Tab>('problems')
  const [stats, setStats] = useState<DbStats | null>(null)
  const [rows, setRows] = useState<ProblemRow[]>([])
  const [filter, setFilter] = useState<'all' | 'open' | 'resolved'>('all')
  const [detail, setDetail] = useState<ProblemDetail | null>(null)
  const [logs, setLogs] = useState<LogRow[]>([])
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<SearchHit | null>(null)
  const [busy, setBusy] = useState(false)
  const [resolution, setResolution] = useState('')

  const load = useCallback(async () => {
    try {
      const d = await api.problems(filter === 'all' ? undefined : filter)
      setStats(d.stats); setRows(d.problems)
      if (tab === 'log') setLogs(await api.logs(300))
    } catch (e) { toast('warning', 'Problem database unavailable', (e as Error).message) }
  }, [filter, tab, toast])
  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (openId == null) { setDetail(null); return }
    api.problem(openId).then(setDetail).catch(e => toast('warning', 'Could not load problem', (e as Error).message))
    setResolution('')
  }, [openId, toast])

  async function runSearch() {
    if (!q.trim()) return
    setBusy(true)
    try { setHits(await api.searchProblems(q.trim())) } catch (e) { toast('warning', 'Search failed', (e as Error).message) }
    setBusy(false)
  }

  async function resolve() {
    if (!detail || !resolution.trim()) return
    try {
      setDetail(await api.resolveProblem(detail.problem_id, resolution.trim()))
      toast('success', `Problem #${detail.problem_id} resolved`, 'Recorded in the problem database'); load()
    } catch (e) { toast('warning', 'Resolve failed', (e as Error).message) }
  }

  async function reopen() {
    if (!detail) return
    try { setDetail(await api.reopenProblem(detail.problem_id)); load() } catch (e) { toast('warning', 'Reopen failed', (e as Error).message) }
  }

  const tabs: [Tab, string][] = [['problems', 'Problems'], ['search', 'Search'], ['log', 'Triage log']]
  return (
    <div className="space-y-5">
      <PageHeader title="Problem database" sub="Every ticket the system has handled, grouped into distinct problems" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <MetricCard label="Tickets logged" value={stats?.tickets_logged ?? '—'} />
        <MetricCard label="Distinct problems" value={stats?.problems ?? '—'} />
        <MetricCard label="Reported more than once" value={stats?.recurring_problems ?? '—'} />
        <MetricCard label="Open" value={stats?.open_problems ?? '—'} />
        <MetricCard label="Resolved" value={stats?.resolved_problems ?? '—'} />
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {tabs.map(([k, label]) => (
          <button key={k} onClick={() => { setTab(k); setOpenId(null) }}
            className={`px-3 py-2 text-sm font-medium ${tab === k ? 'border-b-2 border-coral text-navy' : 'text-slate-500 hover:text-navy'}`}>{label}</button>
        ))}
      </div>

      {tab === 'problems' && (detail ? (
        <Card className="space-y-4 p-5">
          <button onClick={() => setOpenId(null)} className="text-sm text-slate-500 hover:text-navy">← All problems</button>
          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-sm font-semibold text-coral">#{detail.problem_id}</span>
            <h2 className="text-lg font-bold text-navy">{detail.title}</h2>
            <span className={`rounded px-2 py-0.5 text-xs font-semibold ${detail.status === 'resolved' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{detail.status}</span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <div><div className="text-xs text-slate-500">Reported</div>{detail.occurrences}×</div>
            <div><div className="text-xs text-slate-500">Team</div>{detail.queue || '—'}</div>
            <div><div className="text-xs text-slate-500">Priority</div>{detail.priority || '—'}</div>
            <div><div className="text-xs text-slate-500">First / last seen</div>{detail.first_seen.slice(0, 16)} / {detail.last_seen.slice(0, 16)}</div>
          </div>
          <p className="whitespace-pre-wrap rounded bg-slate-50 p-3 text-sm text-slate-700">{detail.text}</p>
          {detail.status === 'resolved' ? (
            <div className="space-y-2">
              <p className="flex gap-2 text-sm"><CheckCircle2 size={16} className="text-emerald-600" />
                Resolved by {detail.resolved_by} {detail.precedent_id && <>· knowledge-base precedent <b>{detail.precedent_id}</b></>}</p>
              <p className="text-sm text-slate-700">{detail.resolution}</p>
              <button onClick={reopen} className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-navy"><RotateCcw size={14} />Reopen</button>
            </div>
          ) : (
            <div className="space-y-2">
              <textarea value={resolution} onChange={e => setResolution(e.target.value)} rows={3}
                placeholder="Resolution for this problem" className="w-full rounded border border-slate-300 p-2 text-sm" />
              <button onClick={resolve} disabled={!resolution.trim()}
                className="rounded bg-navy px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">Mark problem resolved</button>
            </div>
          )}
          <div>
            <div className="mb-1 text-xs font-medium text-slate-500">Tickets attached to this problem</div>
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500"><tr><th>#</th><th>When</th><th>Subject</th><th>Similarity</th><th>Gate</th></tr></thead>
              <tbody>{detail.tickets.map(x => (
                <tr key={x.log_id} className="border-t border-slate-100"><td>{x.log_id}</td><td>{x.ts.slice(0, 16)}</td>
                  <td className="truncate">{x.subject || x.body.slice(0, 60)}</td><td>{x.similarity.toFixed(2)}</td><td>{x.status}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card className="p-5">
          <div className="mb-3 flex gap-2">
            {(['all', 'open', 'resolved'] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${filter === f ? 'bg-navy text-white' : 'bg-slate-100 text-slate-600'}`}>{f}</button>
            ))}
          </div>
          {rows.length === 0 ? <p className="text-sm text-slate-500">No problems yet. Submit a ticket and it appears here.</p> : (
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500"><tr><th>#</th><th>Title</th><th>Team</th><th>Priority</th><th>Reported</th><th>Status</th><th>Last seen</th></tr></thead>
              <tbody>{rows.map(r => (
                <tr key={r.problem_id} onClick={() => setOpenId(r.problem_id)} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
                  <td className="font-mono text-coral">{r.problem_id}</td><td className="max-w-xs truncate">{r.title}</td><td>{r.queue}</td>
                  <td>{r.priority}</td><td>{r.occurrences}×</td><td>{r.status}</td><td>{r.last_seen.slice(0, 16)}</td></tr>
              ))}</tbody>
            </table>
          )}
        </Card>
      ))}

      {tab === 'search' && (
        <Card className="space-y-4 p-5">
          <p className="text-sm text-slate-500">Check whether a problem is already known. Searching records nothing.</p>
          <div className="flex gap-2">
            <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && runSearch()}
              placeholder="e.g. Outlook stopped receiving new emails" className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm" />
            <button onClick={runSearch} disabled={busy || !q.trim()}
              className="inline-flex items-center gap-1.5 rounded bg-navy px-3 py-2 text-sm font-semibold text-white disabled:opacity-40">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}Search</button>
          </div>
          {hits && (<>
            {hits.problems[0]?.same_problem
              ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                  Known problem <b>#{hits.problems[0].problem_id}</b>: {hits.problems[0].title} ({hits.problems[0].status}, reported {hits.problems[0].occurrences}×)
                  {hits.problems[0].resolution && <div className="mt-1">Resolution: {hits.problems[0].resolution}</div>}</div>
              : <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Not in the problem database yet. It will be added when a ticket like this is submitted.</div>}
            <div>
              <div className="mb-1 text-xs font-medium text-slate-500">Most related problems in the database</div>
              {hits.problems.length === 0 ? <p className="text-sm text-slate-400">None above 0.80 similarity.</p> : (
                <ul className="space-y-1 text-sm">{hits.problems.map(p => (
                  <li key={p.problem_id} className="flex justify-between rounded border border-slate-100 px-3 py-1.5">
                    <span>#{p.problem_id} {p.title}</span><span className="font-mono text-xs text-slate-500">{p.similarity.toFixed(2)} · {p.occurrences}× · {p.status}</span></li>))}</ul>)}
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-slate-500">Most related resolved tickets (knowledge base)</div>
              <ul className="space-y-1 text-sm">{hits.precedents.map(p => (
                <li key={p.ticket_id} className="rounded border border-slate-100 px-3 py-1.5">
                  <span className="font-mono text-coral">{p.ticket_id}</span> <span className="font-mono text-xs text-slate-500">{p.score.toFixed(3)} · {p.language}</span>
                  <div className="truncate text-slate-600">{p.subject || p.answer}</div></li>))}</ul>
            </div>
          </>)}
        </Card>
      )}

      {tab === 'log' && (
        <Card className="overflow-x-auto p-5">
          {logs.length === 0 ? <p className="text-sm text-slate-500">Nothing logged yet.</p> : (
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500"><tr><th>#</th><th>When</th><th>Problem</th><th>Subject</th><th>Type</th><th>Team</th><th>Gate</th><th>Top-1 sim</th><th>Latency</th></tr></thead>
              <tbody>{logs.map(l => (
                <tr key={l.log_id} className="border-t border-slate-100"><td>{l.log_id}</td><td>{l.ts.slice(0, 16)}</td>
                  <td>{l.problem_id != null ? `#${l.problem_id}${l.is_new_problem ? ' (new)' : ''}` : '—'}</td>
                  <td className="max-w-xs truncate">{l.subject}</td><td>{l.type}</td><td>{l.queue}</td><td>{l.status}</td>
                  <td>{l.top1_similarity?.toFixed(3) ?? '—'}</td><td>{Math.round(l.latency_ms)} ms</td></tr>
              ))}</tbody>
            </table>
          )}
        </Card>
      )}
    </div>
  )
}
