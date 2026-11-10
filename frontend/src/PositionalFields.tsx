import type { SkyObject } from './report.ts'

/** The moment in the browser's time zone, like "3:11 PM". Reports are requested for that same
 * zone (see report.ts), so it is the zone the night was computed for. */
export function LocalTime({ moment }: { moment: string }) {
  const text = new Date(moment).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
  return <time dateTime={moment}>{text}</time>
}

const COMPASS_POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

/** "55°": whole degrees are as fine as anyone can point by eye. */
export function Altitude({ degrees }: { degrees: number }) {
  return <>{Math.round(degrees)}°</>
}

/** "132° SE": the bearing, and the nearest of the eight compass points. */
export function Azimuth({ degrees }: { degrees: number }) {
  const point = COMPASS_POINTS[Math.round(degrees / 45) % COMPASS_POINTS.length]
  return <>{`${Math.round(degrees) % 360}° ${point}`}</>
}

/** "-2.0": magnitude to a tenth, or "-" when the body has none (a constellation). */
export function Magnitude({ magnitude }: { magnitude: number | null }) {
  return <>{magnitude === null ? '-' : magnitude.toFixed(1)}</>
}

/** A rise time, or that the body is already up and doesn't rise during the Viewing Window. */
export function RiseTime({ moment }: { moment: string | null }) {
  return moment ? <LocalTime moment={moment} /> : <>Doesn't rise tonight</>
}

/** A set time, or that the body stays up and doesn't set during the Viewing Window. */
export function SetTime({ moment }: { moment: string | null }) {
  return moment ? <LocalTime moment={moment} /> : <>Doesn't set tonight</>
}

/** A body's positional fields, as rows of a description list. */
export function PositionalFields({ body }: { body: SkyObject }) {
  return (
    <>
      <dt>Peak altitude</dt>
      <dd>
        <Altitude degrees={body.peak_altitude_degrees} />
      </dd>
      <dt>Direction at peak</dt>
      <dd>
        <Azimuth degrees={body.azimuth_at_peak_degrees} />
      </dd>
      <dt>Rises</dt>
      <dd>
        <RiseTime moment={body.rises_at} />
      </dd>
      <dt>Sets</dt>
      <dd>
        <SetTime moment={body.sets_at} />
      </dd>
      <dt>Magnitude</dt>
      <dd>
        <Magnitude magnitude={body.magnitude} />
      </dd>
    </>
  )
}
