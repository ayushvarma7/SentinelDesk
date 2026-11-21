import { ArrowRight, LifeBuoy } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { makeUser } from '../api'
import { useT } from '../i18n'
import type { User } from '../types'
import { LangToggle } from './Header'

export function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const t = useT()
  const [value, setValue] = useState('')
  const [error, setError] = useState(false)

  function submit(e: FormEvent) {
    e.preventDefault()
    const u = makeUser(value)
    if (!u) return setError(true)
    onLogin(u)
  }

  return (
    <div className="flex min-h-screen flex-col bg-navy">
      <div className="flex justify-end p-4 sm:p-6">
        <LangToggle />
      </div>
      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-md fade-up">
          <div className="mb-8 flex flex-col items-center text-center text-white">
            <span className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-coral shadow-lg shadow-coral/30">
              <LifeBuoy size={28} />
            </span>
            <h1 className="text-2xl font-semibold tracking-tight">{t('loginTitle')}</h1>
            <p className="mt-2 text-sm text-white/70">{t('loginSub')}</p>
          </div>
          <form onSubmit={submit} noValidate className="rounded-2xl bg-white p-6 shadow-xl sm:p-8">
            <label htmlFor="login" className="mb-1.5 block text-sm font-medium text-slate-700">{t('loginLabel')}</label>
            <input
              id="login"
              autoFocus
              autoComplete="username"
              value={value}
              onChange={(e) => { setValue(e.target.value); setError(false) }}
              placeholder={t('loginPlaceholder')}
              maxLength={254}
              aria-invalid={error}
              className={`w-full rounded-xl border px-4 py-3 text-sm outline-none transition focus:ring-4 ${
                error ? 'border-coral focus:ring-coral/15' : 'border-slate-300 focus:border-navy-3 focus:ring-navy/10'
              }`}
            />
            {error && <p role="alert" className="mt-2 text-sm text-coral-dark">{t('loginInvalid')}</p>}
            <button
              type="submit"
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-coral px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-coral-dark"
            >
              {t('loginButton')} <ArrowRight size={16} />
            </button>
            <p className="mt-4 text-center text-xs text-slate-500">{t('loginDemo')}</p>
          </form>
        </div>
      </div>
    </div>
  )
}
