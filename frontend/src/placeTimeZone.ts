import { createContext, useContext } from 'react'

/** The IANA zone of the place a report is for, which every time in it is shown in. Without a
 * provider, times fall back to the browser's own zone. */
export const PlaceTimeZone = createContext<string | undefined>(undefined)

export function usePlaceTimeZone(): string | undefined {
  return useContext(PlaceTimeZone)
}

/** The moment on the place's clock, like "3:11 PM". When the browser's clock reads a different
 * zone at that moment, the place's zone is named too, like "3:11 PM GMT+9", so a time is never
 * mistaken for the viewer's own. Each moment is labelled for itself, so a clock change overnight
 * shows as one. */
export function placeTime(moment: string, timeZone: string | undefined): string {
  const date = new Date(moment)
  const named = zoneName(date, timeZone) !== zoneName(date, browserTimeZone())
  return date.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
    timeZoneName: named ? 'short' : undefined,
  })
}

function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}

function zoneName(date: Date, timeZone: string | undefined): string | undefined {
  return new Intl.DateTimeFormat(undefined, { timeZone, timeZoneName: 'short' })
    .formatToParts(date)
    .find((part) => part.type === 'timeZoneName')?.value
}
