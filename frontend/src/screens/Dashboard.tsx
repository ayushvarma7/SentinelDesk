import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, LabelList } from 'recharts'
import { Activity, Gauge, ShieldAlert, Target } from 'lucide-react'
import type { Metrics } from '../api'
import { useT } from '../i18n'
import { Card, Skeleton } from '../ui'

// Validated (dataviz validate_palette.js, light): red / amber / green pass CVD + normal-vision checks.
// Amber is < 3:1 against white, so the donut carries visible labels and a legend.
const PRIO_COLOR: Record<string, string> = { high: '#D93F35', medium: '#E0A021', low: '#2E9E5B' }
const NAVY = '#1E3A66'
const AXIS = { fontSize: 12, fill: '#64748b' }

export default function Dashboard({ m }: { m: Metrics | null }) {
  const t = useT()
  if (!m) return (
    <div className="space-y-5">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map(i => <Card key={i} className="space-y-3 p-5"><Skeleton className="h-4 w-32" /><Skeleton className="h-8 w-24" /></Card>)}</div>
      <div className="grid gap-4 lg:grid-cols-2">{[0, 1].map(i => <Card key={i} className="p-5"><Skeleton className="h-[260px]" /></Card>)}</div>
    </div>
  )

  const prio = (['high', 'medium', 'low'] as const).map(k => ({ key: k, name: t(k), value: m.by_priority[k] ?? 0 }))
  const queues = Object.entries(m.by_queue).map(([name, value]) => ({ name, value }))
  const outcome = [
    { name: t('autoResolved'), value: m.auto_resolved, fill: '#0F8F84' },
    { name: t('escalated'), value: m.escalated, fill: '#F0584A' },
    { name: t('total'), value: m.total, fill: NAVY },
  ]
  const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-navy">{t('dashboard')}</h1>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={<Activity size={18} />} label={t('total')} value={String(m.total)} />
        <Kpi icon={<ShieldAlert size={18} />} label={t('escRate')} value={pct(m.escalation_rate)} sub={`${m.escalated} / ${m.total}`} />
        <Kpi icon={<Gauge size={18} />} label={t('avgLatency')} value={`${m.avg_latency_ms.toFixed(0)} ms`} sub={m.mode === 'mock' ? 'mock timings' : 'live pipeline'} />
        <Kpi icon={<Target size={18} />} label={t('recall')} value={pct(m.kpi.high_priority_incident_recall)}
          sub={m.kpi.high_priority_incident_recall == null ? undefined
            : `${t('holdout')}${m.kpi.high_incident_escalated != null ? ` · ${t('gateEsc')} ${pct(m.kpi.high_incident_escalated)} ${t('ofHighInc')}` : ''}`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title={t('byPriority')}>
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-center">
            <div className="relative h-[240px] w-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={prio} dataKey="value" nameKey="name" innerRadius={70} outerRadius={110} paddingAngle={1.5}
                    stroke="#fff" strokeWidth={2} startAngle={90} endAngle={-270}>
                    {prio.map(p => <Cell key={p.key} fill={PRIO_COLOR[p.key]} />)}
                  </Pie>
                  <Tooltip formatter={(v, n) => [`${v} (${m.total ? Math.round(Number(v) / m.total * 100) : 0}%)`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-bold tabular-nums text-navy">{m.total}</span>
                <span className="text-xs text-slate-500">{t('tickets')}</span>
              </div>
            </div>
            {/* legend doubles as the data table: label + count + share, so identity never relies on colour */}
            <ul className="min-w-[160px] space-y-2.5">
              {prio.map(p => (
                <li key={p.key} className="flex items-center gap-2.5 text-sm">
                  <span className="h-3 w-3 rounded-sm" style={{ background: PRIO_COLOR[p.key] }} />
                  <span className="flex-1 text-slate-700">{p.name}</span>
                  <span className="font-semibold tabular-nums text-slate-900">{p.value}</span>
                  <span className="w-10 text-right text-xs tabular-nums text-slate-500">{m.total ? Math.round(p.value / m.total * 100) : 0}%</span>
                </li>
              ))}
            </ul>
          </div>
        </ChartCard>

        <ChartCard title={t('outcome')}>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={outcome} margin={{ top: 20, right: 10, left: -10, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid vertical={false} stroke="#eef2f7" />
              <XAxis dataKey="name" tick={AXIS} axisLine={false} tickLine={false} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip cursor={{ fill: '#f1f5f9' }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={56}>
                {outcome.map(o => <Cell key={o.name} fill={o.fill} />)}
                <LabelList dataKey="value" position="top" className="fill-slate-700 text-xs" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard title={t('byQueue')}>
        <ResponsiveContainer width="100%" height={Math.max(220, queues.length * 36)}>
          <BarChart data={queues} layout="vertical" margin={{ top: 0, right: 40, left: 10, bottom: 0 }}>
            <CartesianGrid horizontal={false} stroke="#eef2f7" />
            <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis type="category" dataKey="name" width={210} tick={AXIS} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: '#f1f5f9' }} />
            <Bar dataKey="value" fill={NAVY} radius={[0, 4, 4, 0]} barSize={18}>
              <LabelList dataKey="value" position="right" className="fill-slate-700 text-xs" />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  )
}

function Kpi({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-500"><span className="text-coral">{icon}</span>{label}</div>
      <div className="mt-2 text-3xl font-bold tabular-nums text-navy">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </Card>
  )
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <Card className="p-5"><div className="mb-3 font-semibold text-navy">{title}</div>{children}</Card>
}
