import { useId, useState } from 'react'
import { LocalTime, PositionalFields } from './PositionalFields.tsx'
import type { Highlight, SignificantEvent } from './report.ts'

export function HighlightList({ highlights }: { highlights: Highlight[] }) {
  return (
    <section className="highlights">
      {highlights.map((highlight) => (
        <HighlightCard key={highlight.id} highlight={highlight} />
      ))}
    </section>
  )
}

function HighlightCard({ highlight }: { highlight: Highlight }) {
  const headingId = useId()
  return (
    <article className="highlight-card" aria-labelledby={headingId}>
      <h2 id={headingId}>{highlight.mini_headline}</h2>
      <p>{highlight.paragraph}</p>
      <DetailLayer highlight={highlight} />
    </article>
  )
}

/** The Highlight Card's Detail Layer, expanded and collapsed in place by its Details toggle.
 * Collapsed, only the toggle is rendered. */
function DetailLayer({ highlight }: { highlight: Highlight }) {
  const [expanded, setExpanded] = useState(false)
  const toggleId = useId()
  const regionId = useId()
  return (
    <>
      <button
        type="button"
        id={toggleId}
        className="detail-toggle"
        aria-expanded={expanded}
        aria-controls={regionId}
        onClick={() => setExpanded(!expanded)}
      >
        Details
      </button>
      {expanded && (
        <section id={regionId} className="detail-layer" aria-labelledby={toggleId}>
          <dl>
            {highlight.event && <EventFields event={highlight.event} />}
            <PositionalFields body={highlight} />
          </dl>
        </section>
      )}
    </>
  )
}

/** What a Significant Event is, what it involves, and when it peaks. */
function EventFields({ event }: { event: SignificantEvent }) {
  return (
    <>
      <dt>Event</dt>
      <dd>{EVENT_LABELS[event.event_type].name}</dd>
      {event.related_object_names && (
        <>
          <dt>{EVENT_LABELS[event.event_type].bodies}</dt>
          <dd>{joinNames(event.related_object_names)}</dd>
        </>
      )}
      <dt>Peak</dt>
      <dd>
        <LocalTime moment={event.peak_time} />
      </dd>
    </>
  )
}

/** How the Detail Layer names each event type, and the bodies it involves. */
const EVENT_LABELS: Record<SignificantEvent['event_type'], { name: string; bodies: string }> = {
  conjunction: { name: 'Conjunction', bodies: 'Bodies' },
  opposition: { name: 'Opposition', bodies: 'Planet' },
  meteor_shower: { name: 'Meteor shower', bodies: 'Radiant' },
}

/** "Jupiter and Saturn", or "Mars, Jupiter and Saturn". */
function joinNames(names: string[]): string {
  return new Intl.ListFormat('en', { type: 'conjunction' }).format(names)
}
