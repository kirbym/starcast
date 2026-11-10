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
      {/* So far only a Significant Event has a Detail Layer; #21 gives one to every card. */}
      {highlight.event && <DetailLayer event={highlight.event} />}
    </article>
  )
}

/** The card's Detail Layer, expanded and collapsed in place. Collapsed, it renders nothing. */
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
            {event.related_object_names && (
              <>
                <dt>Bodies</dt>
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

/** "Jupiter and Saturn", or "Mars, Jupiter and Saturn". */
function joinNames(names: string[]): string {
  return new Intl.ListFormat('en', { type: 'conjunction' }).format(names)
}

/** The moment in the observer's own time zone, like "3:11 PM". */
function localTime(moment: string): string {
  return new Date(moment).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}
