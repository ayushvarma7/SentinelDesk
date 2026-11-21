import { useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AlertCircle, Bot, ClipboardList, Loader2, LogOut, MessageCircle, Search, Send, Wrench, X } from 'lucide-react'
import { api, type Ticket } from '../api'
import { LangContext, useT } from '../i18n'
import { Card, CitedText, PrecedentModal, StatusPill, fmtDate } from '../ui'
import type { Precedent } from '../api'

type Msg = { from: 'bot' | 'me'; text: string; ticket?: Ticket; pending?: boolean }

export default function Portal() {
  const t = useT()
  const { lang } = useContext(LangContext)
  const [user, setUser] = useState<string>(() => { try { return localStorage.getItem('sd_user') ?? '' } catch { return '' } })
  const [login, setLogin] = useState('')
  const [mine, setMine] = useState<Ticket[]>([])
  const [q, setQ] = useState('')
  const [form, setForm] = useState<null | 'incident' | 'request'>(null)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [prec, setPrec] = useState<Precedent | null>(null)

  const refresh = useCallback(async () => {
    if (!user) return
    try { setMine(await api.tickets(user)) } catch { /* sidebar just stays stale */ }
  }, [user])
  useEffect(() => { refresh() }, [refresh])
  useEffect(() => { setMsgs([{ from: 'bot', text: t('botHello') }]) }, [lang]) // eslint-disable-line

  const doLogin = (e: React.FormEvent) => {
    e.preventDefault()
    const v = login.trim().toLowerCase()
    if (!v) return
    try { localStorage.setItem('sd_user', v) } catch { /* private mode */ }
    setUser(v)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setErr(null)
    const kind = form ?? 'incident'
    setChatOpen(true)
    setMsgs(m => [...m, { from: 'me', text: subject || body.slice(0, 80) || '(empty)' }, { from: 'bot', text: t('botWorking'), pending: true }])
    try {
      const tk = await api.create({ subject, body, name: user.split('@')[0], email: user, kind })
      await new Promise(r => setTimeout(r, 900)) // let the "analysing" state be visible
      setMsgs(m => [...m.filter(x => !x.pending), botReply(tk)])
      setSubject(''); setBody(''); setForm(null)
      refresh()
    } catch (e2) {
      setErr((e2 as Error).message)
      setMsgs(m => m.filter(x => !x.pending))
    } finally { setBusy(false) }
  }

  const botReply = (tk: Ticket): Msg => {
    const reply = !tk.escalated ? (tk.final_reply ?? tk.triage.draft_reply) : null
    return reply
      ? { from: 'bot', text: `${t('botResolved')} ${tk.id}:`, ticket: { ...tk, final_reply: reply } }
      : { from: 'bot', text: `${t('botEscalated')} ${tk.id}.`, ticket: tk }
  }

  if (!user) return (
    <div className="mx-auto mt-16 max-w-md">
      <Card className="p-8">
        <div className="mb-6 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-navy text-white"><MessageCircle size={20} /></span>
          <h1 className="text-xl font-bold text-navy">{t('loginTitle')}</h1>
        </div>
        <form onSubmit={doLogin} className="space-y-3">
          <input autoFocus value={login} onChange={e => setLogin(e.target.value)} placeholder={t('loginHint')}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-navy focus:ring-2 focus:ring-navy/10" />
          <button className="w-full rounded-lg bg-coral py-2.5 font-semibold text-white hover:bg-coral-dark">{t('signIn')}</button>
        </form>
        <p className="mt-4 text-xs text-slate-500">{t('loginSub')}</p>
      </Card>
    </div>
  )

  const filtered = mine.filter(x => !q.trim() || (x.subject + x.id + x.summary).toLowerCase().includes(q.trim().toLowerCase()))

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-6">
        <div className="rounded-2xl bg-gradient-to-br from-navy to-navy-3 px-8 py-10 text-white">
          <div className="text-sm text-slate-300">{t('welcome')}, {user}</div>
          <h1 className="mt-1 text-2xl font-bold">How can we help?</h1>
          <div className="relative mt-5 max-w-xl">
            <Search size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder={t('searchHelp')}
              className="w-full rounded-xl border-0 py-3 pl-10 pr-4 text-slate-900 outline-none ring-2 ring-transparent focus:ring-coral" />
          </div>
        </div>

        {!form ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {([['incident', Wrench, t('raiseIncident'), t('incidentSub'), 'bg-coral'], ['request', ClipboardList, t('raiseRequest'), t('requestSub'), 'bg-navy']] as const).map(([k, Icon, title, sub, bg]) => (
              <button key={k} onClick={() => setForm(k)} className="group rounded-xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                <span className={`flex h-11 w-11 items-center justify-center rounded-xl text-white ${bg}`}><Icon size={20} /></span>
                <div className="mt-4 text-lg font-semibold text-navy">{title}</div>
                <div className="text-sm text-slate-500">{sub}</div>
              </button>
            ))}
          </div>
        ) : (
          <Card className="p-6">
            <div className="mb-4 text-lg font-semibold text-navy">{form === 'incident' ? t('raiseIncident') : t('raiseRequest')}</div>
            <form onSubmit={submit} className="space-y-3">
              <input value={subject} onChange={e => setSubject(e.target.value)} placeholder={t('subject')} maxLength={500}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-navy" />
              <textarea value={body} onChange={e => setBody(e.target.value)} placeholder={t('body')} rows={6} maxLength={20000}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-navy" />
              {err && <div className="flex items-center gap-1.5 text-sm text-red-600"><AlertCircle size={14} />{err}</div>}
              <div className="flex gap-2">
                <button disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg bg-coral px-5 py-2 font-semibold text-white hover:bg-coral-dark disabled:opacity-50">
                  {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}{t('submit')}
                </button>
                <button type="button" onClick={() => setForm(null)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">{t('cancel')}</button>
              </div>
            </form>
          </Card>
        )}
      </div>

      <aside className="space-y-3">
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="font-semibold text-navy">{t('myTickets')}</div>
            <button onClick={() => { try { localStorage.removeItem('sd_user') } catch { /* ignore */ } setUser(''); setMine([]) }}
              className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-navy"><LogOut size={12} />{t('signOut')}</button>
          </div>
          {filtered.length === 0 && <div className="py-6 text-center text-sm text-slate-400">{t('noTickets')}</div>}
          <ul className="space-y-2">
            {filtered.map(x => (
              <li key={x.id}>
                <button onClick={() => { setChatOpen(true); setMsgs(m => [...m, botReply(x)]) }}
                  className="w-full rounded-lg border border-slate-200 p-3 text-left hover:bg-slate-50">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-navy">{x.id}</span><StatusPill s={x.status} />
                  </div>
                  <div className="mt-1 truncate text-sm text-slate-800">{x.subject}</div>
                  <div className="text-xs text-slate-400">{fmtDate(x.created_at, lang)}</div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </aside>

      {/* floating bot */}
      <button onClick={() => setChatOpen(o => !o)} aria-label="assistant"
        className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-coral text-white shadow-xl hover:bg-coral-dark">
        {chatOpen ? <X size={22} /> : <Bot size={24} />}
      </button>
      {chatOpen && (
        <div className="fixed bottom-24 right-6 z-40 flex h-[480px] w-[360px] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center gap-2 bg-navy px-4 py-3 text-white"><Bot size={18} /><span className="font-semibold">{t('bot')}</span></div>
          <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-3">
            {msgs.map((m, i) => <ChatBubble key={i} m={m} onPrec={setPrec} />)}
            <ScrollAnchor dep={msgs.length} />
          </div>
        </div>
      )}
      <PrecedentModal p={prec} onClose={() => setPrec(null)} />
    </div>
  )
}

function ScrollAnchor({ dep }: { dep: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { ref.current?.scrollIntoView({ behavior: 'smooth' }) }, [dep])
  return <div ref={ref} />
}

function ChatBubble({ m, onPrec }: { m: Msg; onPrec: (p: Precedent) => void }) {
  const mine = m.from === 'me'
  const reply = m.ticket && !m.ticket.escalated ? m.ticket.final_reply : null
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${mine ? 'rounded-br-sm bg-navy text-white' : 'rounded-bl-sm bg-white text-slate-800 shadow-sm ring-1 ring-slate-200'}`}>
        <div className="flex items-center gap-1.5">{m.pending && <Loader2 size={13} className="animate-spin" />}{m.text}</div>
        {m.ticket && <div className="mt-1"><StatusPill s={m.ticket.status} /></div>}
        {reply && <div className="mt-2 border-t border-slate-100 pt-2 text-[13px]"><CitedText text={reply} precedents={m.ticket!.triage.precedents} onOpen={onPrec} /></div>}
      </div>
    </div>
  )
}
