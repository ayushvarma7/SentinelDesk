import { createContext, useContext } from 'react'

export type Lang = 'en' | 'de'

const DICT = {
  en: {
    tickets: 'Tickets', organisation: 'Organisation', portal: 'Customer Portal', dashboard: 'Dashboard',
    id: 'ID', summary: 'Summary', priority: 'Priority', type: 'Type', queue: 'Queue', date: 'Date',
    status: 'Status', assigned: 'Assigned To', tags: 'Tags', confidence: 'Confidence',
    search: 'Search tickets…', allPriorities: 'All priorities', allStatuses: 'All statuses',
    high: 'High', medium: 'Medium', low: 'Low', refresh: 'Refresh', results: 'tickets',
    majorIncident: 'Major incident detected', majorIncidentSub: 'similar tickets within 30 minutes — on-call paged',
    back: 'Back to tickets', needsYou: 'High priority — needs you', needsReview: 'Escalated — needs your review',
    raisedBy: 'Raised by', language: 'Language', sla: 'SLA', slaLeft: 'left', slaBreached: 'SLA breached',
    escalationReasons: 'Why it was escalated', recommended: 'Recommended resolution',
    approve: 'Approve & Send', edit: 'Edit draft', assignMe: 'Assign to me', reject: 'Reject', save: 'Done editing',
    piiMasked: 'PII masked', unverified: 'Unverified claim', handledByAgent: 'Handled by agent',
    agentTrace: 'Agent trace', finalReply: 'Reply sent to customer', draftReply: 'Drafted reply',
    precedents: 'Precedents', override: 'Override', similarity: 'Similarity', answer: 'Resolution',
    ticketBody: 'Customer message', details: 'Details', incId: 'INC ID', name: 'Name', state: 'State',
    created: 'Created', channel: 'Channel', history: 'Activity', noDraft: 'No suggestion available — write a reply manually.',
    signIn: 'Sign in', loginTitle: 'Sign in to the support portal', loginHint: 'Email or phone number',
    loginSub: 'Demo: any email works. Try h.ortiz@stmarys-health.org to see existing tickets.',
    searchHelp: 'Search your tickets…', raiseIncident: 'Raise Incident', raiseRequest: 'Raise Request',
    incidentSub: 'Something is broken or not working', requestSub: 'Ask for access, software or information',
    subject: 'Subject', body: 'Describe the issue', submit: 'Submit', cancel: 'Cancel', myTickets: 'My tickets',
    noTickets: 'No tickets yet.', signOut: 'Sign out', bot: 'Sentinel Assistant',
    botHello: 'Hi! Submit a ticket and I will show you the answer as soon as it is ready.',
    botWorking: 'Analysing your ticket…', botEscalated: 'A specialist is looking at this. Reference',
    botResolved: 'Here is the answer for', welcome: 'Welcome back',
    total: 'Total tickets', escRate: 'Escalation rate', avgLatency: 'Avg triage latency',
    recall: 'High-priority incident recall', byPriority: 'Tickets by priority', byQueue: 'Tickets by queue',
    outcome: 'Auto-resolved vs escalated', autoResolved: 'Auto-resolved', escalated: 'Escalated',
    holdout: 'holdout, predicted high + Incident', gateEsc: 'gate escalates', ofHighInc: 'of high Incidents (validation)',
    mock: 'MOCK', live: 'LIVE', apiDown: 'API not reachable at', loading: 'Loading…', view: 'View',
  },
  de: {
    tickets: 'Tickets', organisation: 'Organisation', portal: 'Kundenportal', dashboard: 'Dashboard',
    id: 'ID', summary: 'Zusammenfassung', priority: 'Priorität', type: 'Typ', queue: 'Warteschlange', date: 'Datum',
    status: 'Status', assigned: 'Zugewiesen an', tags: 'Tags', confidence: 'Konfidenz',
    search: 'Tickets durchsuchen…', allPriorities: 'Alle Prioritäten', allStatuses: 'Alle Status',
    high: 'Hoch', medium: 'Mittel', low: 'Niedrig', refresh: 'Aktualisieren', results: 'Tickets',
    majorIncident: 'Größere Störung erkannt', majorIncidentSub: 'ähnliche Tickets in 30 Minuten — Bereitschaft alarmiert',
    back: 'Zurück zu Tickets', needsYou: 'Hohe Priorität — Sie werden gebraucht', needsReview: 'Eskaliert — bitte prüfen',
    raisedBy: 'Gemeldet von', language: 'Sprache', sla: 'SLA', slaLeft: 'übrig', slaBreached: 'SLA verletzt',
    escalationReasons: 'Grund der Eskalation', recommended: 'Empfohlene Lösung',
    approve: 'Freigeben & senden', edit: 'Entwurf bearbeiten', assignMe: 'Mir zuweisen', reject: 'Ablehnen', save: 'Fertig',
    piiMasked: 'PII maskiert', unverified: 'Nicht belegte Aussage', handledByAgent: 'Vom Agenten bearbeitet',
    agentTrace: 'Agenten-Ablauf', finalReply: 'An Kunden gesendete Antwort', draftReply: 'Antwortentwurf',
    precedents: 'Präzedenzfälle', override: 'Übersteuern', similarity: 'Ähnlichkeit', answer: 'Lösung',
    ticketBody: 'Kundennachricht', details: 'Details', incId: 'INC-ID', name: 'Name', state: 'Status',
    created: 'Erstellt', channel: 'Kanal', history: 'Aktivität', noDraft: 'Kein Vorschlag — bitte manuell antworten.',
    signIn: 'Anmelden', loginTitle: 'Im Supportportal anmelden', loginHint: 'E-Mail oder Telefonnummer',
    loginSub: 'Demo: jede E-Mail funktioniert. h.ortiz@stmarys-health.org zeigt vorhandene Tickets.',
    searchHelp: 'Ihre Tickets durchsuchen…', raiseIncident: 'Störung melden', raiseRequest: 'Anfrage stellen',
    incidentSub: 'Etwas ist defekt oder funktioniert nicht', requestSub: 'Zugriff, Software oder Informationen anfragen',
    subject: 'Betreff', body: 'Beschreiben Sie das Problem', submit: 'Absenden', cancel: 'Abbrechen', myTickets: 'Meine Tickets',
    noTickets: 'Noch keine Tickets.', signOut: 'Abmelden', bot: 'Sentinel-Assistent',
    botHello: 'Hallo! Reichen Sie ein Ticket ein, ich zeige Ihnen die Antwort, sobald sie bereit ist.',
    botWorking: 'Ihr Ticket wird analysiert…', botEscalated: 'Ein Spezialist kümmert sich darum. Referenz',
    botResolved: 'Hier ist die Antwort zu', welcome: 'Willkommen zurück',
    total: 'Tickets gesamt', escRate: 'Eskalationsquote', avgLatency: 'Ø Triage-Latenz',
    recall: 'Recall kritischer Störungen', byPriority: 'Tickets nach Priorität', byQueue: 'Tickets nach Warteschlange',
    outcome: 'Automatisch gelöst vs. eskaliert', autoResolved: 'Automatisch gelöst', escalated: 'Eskaliert',
    holdout: 'Holdout, hoch + Incident vorhergesagt', gateEsc: 'Gate eskaliert', ofHighInc: 'der kritischen Störungen (Validierung)',
    mock: 'MOCK', live: 'LIVE', apiDown: 'API nicht erreichbar unter', loading: 'Lädt…', view: 'Ansehen',
  },
} as const

export type Key = keyof typeof DICT.en
export const LangContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({ lang: 'en', setLang: () => {} })

export function useT() {
  const { lang } = useContext(LangContext)
  return (k: Key) => DICT[lang][k] ?? DICT.en[k]
}

export const STATUS_DE: Record<string, string> = {
  New: 'Neu', 'In Progress': 'In Bearbeitung', 'Auto-Resolved': 'Automatisch gelöst', Escalated: 'Eskaliert', Closed: 'Geschlossen',
}
