import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createApiTicket, ensureMockSeed, health, listApiTickets, mockCreate, mockList, sendFollowUp,
  type NewTicket,
} from './api'
import { Bot } from './components/Bot'
import { Confirmation } from './components/Confirmation'
import { Header } from './components/Header'
import { Home } from './components/Home'
import { Login } from './components/Login'
import { Sidebar } from './components/Sidebar'
import { TicketDetail } from './components/TicketDetail'
import { TicketForm } from './components/TicketForm'
import { DICT, LangCtx, type Lang } from './i18n'
import type { Kind, PublicTicket, User } from './types'

type View =
  | { name: 'home' }
  | { name: 'form'; kind: Kind }
  | { name: 'confirm'; id: string; notice: string | null }
  | { name: 'detail'; id: string }

const POLL_MS = 5000

function initialLang(): Lang {
  try {
    const v = localStorage.getItem('sd-portal-lang')
    if (v === 'en' || v === 'de') return v
  } catch { /* ignore */ }
  return navigator.language?.toLowerCase().startsWith('de') ? 'de' : 'en'
}

export default function App() {
  const [lang, setLangState] = useState<Lang>(initialLang)
  const [user, setUser] = useState<User | null>(null) // fake auth: React state only
  const [offline, setOffline] = useState(false)
  const [tickets, setTickets] = useState<PublicTicket[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>({ name: 'home' })
  const [query, setQuery] = useState('')
  // Fallback copy of the ticket just created, in case an in-flight poll returns a list without it.
  const [lastCreated, setLastCreated] = useState<PublicTicket | null>(null)

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try { localStorage.setItem('sd-portal-lang', l) } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const refresh = useCallback(async (u: User): Promise<PublicTicket[]> => {
    let fromApi: PublicTicket[] = []
    let off = !(await health())
    if (!off) {
      try {
        fromApi = await listApiTickets(u)
      } catch {
        off = true
      }
    }
    if (off) ensureMockSeed(u)
    const all = [...fromApi, ...mockList(u, off)].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    setOffline(off)
    setTickets(all)
    return all
  }, [])

  useEffect(() => {
    if (!user) return
    let alive = true
    const tick = () => { if (alive) void refresh(user) }
    tick()
    const id = setInterval(tick, POLL_MS)
    return () => { alive = false; clearInterval(id) }
  }, [user, refresh])

  const find = useCallback(
    (id: string | null) => (id ? tickets.find((x) => x.id === id) ?? (lastCreated?.id === id ? lastCreated : null) : null),
    [tickets, lastCreated],
  )
  const selected = useMemo(() => find(selectedId), [find, selectedId])
  const viewTicket = useMemo(
    () => (view.name === 'detail' || view.name === 'confirm' ? find(view.id) : null),
    [find, view],
  )

  async function submit(nt: NewTicket) {
    if (!user) return
    let created: PublicTicket
    let notice: string | null = null
    if (offline) {
      created = mockCreate(user, nt)
    } else {
      try {
        created = await createApiTicket(user, nt)
      } catch {
        created = mockCreate(user, nt)
        notice = DICT[lang].submitError
      }
    }
    setLastCreated(created)
    await refresh(user)
    setSelectedId(created.id)
    setView({ name: 'confirm', id: created.id, notice })
  }

  async function followUp(text: string) {
    if (!user || !selected) return
    await sendFollowUp(selected, user, text)
    await refresh(user)
  }

  function open(id: string) {
    setSelectedId(id)
    setView({ name: 'detail', id })
  }

  function signOut() {
    setUser(null)
    setTickets([])
    setSelectedId(null)
    setLastCreated(null)
    setQuery('')
    setView({ name: 'home' })
  }

  let main
  if (view.name === 'form') {
    main = <TicketForm key={view.kind} kind={view.kind} onCancel={() => setView({ name: 'home' })} onSubmit={submit} />
  } else if ((view.name === 'confirm' || view.name === 'detail') && viewTicket) {
    main = view.name === 'confirm'
      ? <Confirmation ticket={viewTicket} notice={view.notice} onView={() => open(viewTicket.id)} onHome={() => setView({ name: 'home' })} />
      : <TicketDetail key={viewTicket.id} ticket={viewTicket} onBack={() => setView({ name: 'home' })} />
  } else {
    main = (
      <Home
        query={query}
        setQuery={setQuery}
        tickets={tickets}
        onNew={(kind) => setView({ name: 'form', kind })}
        onOpen={open}
      />
    )
  }

  return (
    <LangCtx.Provider value={{ lang, setLang }}>
      {!user ? (
        <Login onLogin={setUser} />
      ) : (
        <div className="min-h-screen">
          <Header user={user} offline={offline} onHome={() => setView({ name: 'home' })} onSignOut={signOut} />
          <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 pb-28 sm:px-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:py-8">
            <div className="min-w-0">{main}</div>
            <Sidebar tickets={tickets} selected={selected} onSelect={setSelectedId} onOpen={open} />
          </main>
          <Bot ticket={selected} onFollowUp={followUp} />
        </div>
      )}
    </LangCtx.Provider>
  )
}
