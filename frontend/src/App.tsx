import { useCallback, useEffect, useState } from 'react'
import { BarChart3, LayoutList, ShieldCheck, WifiOff } from 'lucide-react'
import { API_BASE, api, type Metrics, type Ticket } from './api'
import { LangContext, useT, type Lang } from './i18n'
import Tickets from './screens/Tickets'
import Dashboard from './screens/Dashboard'

type Screen = 'tickets' | 'dashboard'

function Shell() {
  const t = useT()
  const [screen, setScreen] = useState<Screen>('tickets')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [mode, setMode] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [down, setDown] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const [ts, m, h] = await Promise.all([api.tickets(), api.metrics(), api.health()])
      setTickets(ts); setMetrics(m); setMode(h.mode); setDown(false)
    } catch { setDown(true) } finally { setLoading(false) }
  }, [])
  useEffect(() => { reload() }, [reload, screen])

  const onUpdate = (tk: Ticket) => {
    setTickets(ts => ts.map(x => (x.id === tk.id ? tk : x)))
    api.metrics().then(setMetrics).catch(() => {})
  }

  const nav: [Screen, string, typeof LayoutList][] = [
    ['tickets', `${t('organisation')} › ${t('tickets')}`, LayoutList],
    ['dashboard', t('dashboard'), BarChart3],
  ]

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-30 bg-navy text-white shadow-md">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-6 px-6">
          <div className="flex items-center gap-2 font-bold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-coral"><ShieldCheck size={18} /></span>
            SentinelDesk
          </div>
          <nav className="flex h-full gap-1">
            {nav.map(([k, label, Icon]) => (
              <button key={k} onClick={() => setScreen(k)}
                className={`relative inline-flex h-full items-center gap-1.5 px-3 text-sm font-medium transition ${screen === k ? 'text-white' : 'text-slate-400 hover:text-slate-200'}`}>
                <Icon size={15} />{label}
                {screen === k && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded bg-coral" />}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {mode && <span title={mode === 'mock' ? 'SD_MOCK=1 or artifacts missing: realistic mock data' : 'Real sentineldesk pipeline'}
              className={`rounded px-2 py-0.5 text-[10px] font-bold tracking-wider ${mode === 'mock' ? 'bg-amber-400 text-navy' : 'bg-emerald-500 text-white'}`}>
              {mode === 'mock' ? t('mock') : t('live')}</span>}
            <LangToggle />
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-navy-3 text-xs font-semibold">YOU</span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-6 py-6">
        {down && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <WifiOff size={16} />{t('apiDown')} <code className="font-mono">{API_BASE}</code> — run <code className="font-mono">./run_dev.sh</code>
          </div>
        )}
        {screen === 'tickets' && <Tickets tickets={tickets} reload={reload} onUpdate={onUpdate} loading={loading} />}
        {screen === 'dashboard' && <Dashboard m={metrics} />}
      </main>
    </div>
  )
}

function LangToggle() {
  return (
    <LangContext.Consumer>
      {({ lang, setLang }) => (
        <div className="flex overflow-hidden rounded-md ring-1 ring-white/20">
          {(['en', 'de'] as Lang[]).map(l => (
            <button key={l} onClick={() => setLang(l)}
              className={`px-2.5 py-1 text-xs font-semibold uppercase ${lang === l ? 'bg-white text-navy' : 'text-slate-300 hover:bg-white/10'}`}>{l}</button>
          ))}
        </div>
      )}
    </LangContext.Consumer>
  )
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => { try { return (localStorage.getItem('sd_lang') as Lang) || 'en' } catch { return 'en' } })
  const set = (l: Lang) => { setLang(l); try { localStorage.setItem('sd_lang', l) } catch { /* ignore */ } }
  return <LangContext.Provider value={{ lang, setLang: set }}><Shell /></LangContext.Provider>
}
