import type { components } from './api/schema.gen.ts'
import type { Location } from './location.ts'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

/** The shapes on the wire, generated from the backend's OpenAPI document by `npm run gen:api`. */
type Schemas = components['schemas']

export type SignificantEvent = Schemas['SignificantEvent']

/** A Visible body and its positional fields: one entry of `visible_objects`. `rises_at` is null
 * when the body never set before its peak, and `sets_at` when it stays up after it. */
export type VisibleBody = Schemas['VisibleBody']

/** What the Cosmic Report shows for one Highlight: its Visible body, mini-headline and paragraph. */
export type HighlightCard = Schemas['HighlightCard']

export type ViewingWindow = Schemas['ViewingWindow']

export type CosmicReport = Schemas['ReportResponse']

function localDate(now: Date): string {
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Request tonight's Cosmic Report for a location, on the local date. */
export async function fetchReport(location: Location): Promise<CosmicReport> {
  const response = await fetch(`${API_BASE_URL}/api/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      latitude: location.latitude,
      longitude: location.longitude,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      date: localDate(new Date()),
      location_label: location.label,
    }),
  })
  if (!response.ok) throw await parseReportError(response)
  return response.json()
}

/**
 * The error `type`s the backend's `{error: {statusCode, type, message}}` envelope can carry.
 * `invalid_location` blames the user's place (its latitude or longitude); `invalid_request` blames
 * the rest of the request, which the browser made, so the place is still good.
 */
const REPORT_ERROR_TYPES = [
  'invalid_location',
  'invalid_request',
  'narration_failed',
  'internal_error',
] as const

export type ReportErrorType = (typeof REPORT_ERROR_TYPES)[number]

/**
 * A report request the backend refused or failed. `message` is the backend's
 * own, for the console only: it is never shown to the user.
 */
export class ReportError extends Error {
  readonly type: ReportErrorType
  readonly statusCode: number

  constructor(statusCode: number, type: ReportErrorType, message: string) {
    super(message)
    this.name = 'ReportError'
    this.statusCode = statusCode
    this.type = type
  }
}

async function parseReportError(response: Response): Promise<ReportError> {
  const fallback = `Report request failed with status ${response.status}`
  try {
    const { error } = (await response.json()) as {
      error?: { type?: unknown; message?: unknown }
    }
    if (isReportErrorType(error?.type)) {
      const message = typeof error.message === 'string' ? error.message : fallback
      return new ReportError(response.status, error.type, message)
    }
  } catch {
    // Not the error envelope; treated as the backend failing.
  }
  return new ReportError(response.status, 'internal_error', fallback)
}

function isReportErrorType(value: unknown): value is ReportErrorType {
  return (REPORT_ERROR_TYPES as readonly unknown[]).includes(value)
}
