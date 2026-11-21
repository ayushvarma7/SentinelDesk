/** SentinelDesk mark: a shield with a check-pulse. Same artwork as public/favicon.svg. */
export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#F0584A" />
      <path d="M16 6.5 24 9.4v6.1c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V9.4L16 6.5Z" fill="none" stroke="#fff" strokeWidth="2" strokeLinejoin="round" />
      <path d="M11.2 16.2h2.6l1.5-2.8 2.4 5 1.4-2.2h1.7" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      <div className="leading-none">
        <div className="text-[15px] font-bold tracking-tight text-white">Sentinel<span className="text-coral">Desk</span></div>
        <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">Service Management</div>
      </div>
    </div>
  )
}
