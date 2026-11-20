import { createContext, useContext } from 'react'

/** The IANA zone of the place a report is for, which every time in it is shown in. Without a
 * provider, times fall back to the browser's own zone. */
export const PlaceTimeZone = createContext<string | undefined>(undefined)

export function usePlaceTimeZone(): string | undefined {
  return useContext(PlaceTimeZone)
}

/** The place's zone, like "GMT+9", when the browser's clock reads differently at `moment`; null
 * when they agree, so the times need no label. */
export function usePlaceZoneLabel(moment: string): string | null {
  const timeZone = usePlaceTimeZone()
  if (timeZone === undefined) return null
  const place = zoneName(timeZone, moment)
  return place === zoneName(undefined, moment) ? null : (place ?? timeZone)
}

function zoneName(timeZone: string | undefined, moment: string): string | undefined {
  return new Intl.DateTimeFormat(undefined, { timeZone, timeZoneName: 'short' })
    .formatToParts(new Date(moment))
    .find((part) => part.type === 'timeZoneName')?.value
}
