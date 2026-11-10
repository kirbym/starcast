import { useId, useState } from 'react'

export type SignificantEvent = {
  event_type: 'conjunction' | 'opposition' | 'meteor_shower'
  peak_time: string
  related_object_names: string[] | null
}

export type Highlight = {
  id: string
  name: string
  mini_headline: string
  paragraph: string
  event: SignificantEvent | null
}

export function HighlightList({ highlights }: { highlights: Highlight[] }) {
  if (highlights.length === 0) return null
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
      {/* So far only a Significant Event has a Detail Layer; #21 gives one to every Highlight Card. */}
      {highlight.event && <DetailLayer event={highlight.event} />}
    </article>
  )
}

/** The Highlight Card's Detail Layer, expanded and collapsed in place by its Details toggle.
 * Collapsed, only the toggle is rendered. */
function DetailLayer({ event }: { event: SignificantEvent }) {
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
            <dt>Event</dt>
            <dd>{EVENT_NAMES[event.event_type]}</dd>
            {event.related_object_names && (
              <>
                <dt>{event.event_type === 'opposition' ? 'Planet' : 'Bodies'}</dt>
                <dd>{joinNames(event.related_object_names)}</dd>
              </>
            )}
            <dt>Peak</dt>
            <dd>
              <time dateTime={event.peak_time}>{localTime(event.peak_time)}</time>
            </dd>
          </dl>
        </section>
      )}
    </>
  )
}

const EVENT_NAMES: Record<SignificantEvent['event_type'], string> = {
  conjunction: 'Conjunction',
  opposition: 'Opposition',
  meteor_shower: 'Meteor shower',
}

/** "Jupiter and Saturn", or "Mars, Jupiter and Saturn". */
function joinNames(names: string[]): string {
  return new Intl.ListFormat('en', { type: 'conjunction' }).format(names)
}

/** The moment in the browser's time zone, like "3:11 PM". Reports are requested for that same
 * zone (see report.ts), so it is the zone the night was computed for. */
function localTime(moment: string): string {
  return new Date(moment).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}
