import { useId, useState } from 'react'
import { Altitude, Azimuth, LocalTime, Magnitude, RiseTime, SetTime } from './PositionalFields.tsx'
import type { SkyObject, ViewingWindow } from './report.ts'

/** The Detail Layer's shared part, shown once below the cards: the night's Viewing Window, and
 * the other Visible objects with their positional fields. Objects on a card are left to the card,
 * so the two parts never repeat each other. The list starts collapsed, so the Casual Layer carries
 * no positional data. */
export function VisibleObjects({
  viewingWindow,
  objects,
}: {
  viewingWindow: ViewingWindow
  objects: SkyObject[]
}) {
  const [expanded, setExpanded] = useState(false)
  const headingId = useId()
  const listId = useId()
  return (
    <section className="visible-objects" aria-labelledby={headingId}>
      <h2 id={headingId}>Also visible tonight</h2>
      <p className="viewing-window">
        Dark from <LocalTime moment={viewingWindow.starts_at} /> to{' '}
        <LocalTime moment={viewingWindow.ends_at} />
      </p>
      {objects.length > 0 && (
        <button
          type="button"
          className="detail-toggle"
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Hide' : `Show all ${objects.length}`}
        </button>
      )}
      {expanded && (
        <div id={listId} className="visible-objects-table">
          <table>
            <thead>
              <tr>
                <th scope="col">Object</th>
                <th scope="col">Peak altitude</th>
                <th scope="col">Direction at peak</th>
                <th scope="col">Rises</th>
                <th scope="col">Sets</th>
                <th scope="col">Magnitude</th>
              </tr>
            </thead>
            <tbody>
              {objects.map((body) => (
                <tr key={body.id}>
                  <th scope="row">{body.name}</th>
                  <td>
                    <Altitude degrees={body.peak_altitude_degrees} />
                  </td>
                  <td>
                    <Azimuth degrees={body.azimuth_at_peak_degrees} />
                  </td>
                  <td>
                    <RiseTime moment={body.rises_at} />
                  </td>
                  <td>
                    <SetTime moment={body.sets_at} />
                  </td>
                  <td>
                    <Magnitude magnitude={body.magnitude} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
