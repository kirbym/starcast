import { useId, useState } from 'react'
import { LocalTime, PositionalFields } from './PositionalFields.tsx'
import type { HighlightCard, SignificantEvent } from './report.ts'

export function HighlightList({ highlights }: { highlights: HighlightCard[] }) {
  return (
    <section className="highlights">
      {highlights.map((highlight) => (
        <Card key={highlight.id} highlight={highlight} />
      ))}
    </section>
  )
}

function Card({ highlight }: { highlight: HighlightCard }) {
  const headingId = useId()
  return (
    <article className="highlight-card" aria-labelledby={headingId}>
      <h2 id={headingId}>
        {highlight.mini_headline} <span className="highlight-kind">{kindLabel(highlight)}</span>
      </h2>
      <p>{highlight.paragraph}</p>
      <DetailLayer highlight={highlight} />
    </article>
  )
}

/** What kind of Visible body a Highlight Card describes, as its title's closing label: the
 * event's own kind for a Significant Event, so every Highlight Card says exactly what it is. */
function kindLabel(highlight: HighlightCard): string {
  if (highlight.object_type === 'significant_event' && highlight.event) {
    return EVENT_LABELS[highlight.event.event_type].name
  }
  return KIND_LABELS[highlight.object_type]
}

/** How a Highlight Card's title labels each kind of Visible body. */
const KIND_LABELS: Record<HighlightCard['object_type'], string> = {
  planet: 'Planet',
  moon: 'Moon',
  constellation: 'Constellation',
  bright_star: 'Bright Star',
  named_comet: 'Comet',
  dso: 'Deep-Sky Object',
  significant_event: 'Event',
}

/** The Highlight Card's Detail Layer, expanded and collapsed in place by its Details toggle.
 * Collapsed, only the toggle is rendered. */
function DetailLayer({ highlight }: { highlight: HighlightCard }) {
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

/** How each event type is named, in the Detail Layer and on its Highlight Card's title, and
 * what the Detail Layer calls the bodies it involves. */
const EVENT_LABELS: Record<SignificantEvent['event_type'], { name: string; bodies: string }> = {
  conjunction: { name: 'Conjunction', bodies: 'Bodies' },
  opposition: { name: 'Opposition', bodies: 'Planet' },
  meteor_shower: { name: 'Meteor Shower', bodies: 'Radiant' },
}

/** "Jupiter and Saturn", or "Mars, Jupiter and Saturn". */
function joinNames(names: string[]): string {
  return new Intl.ListFormat('en', { type: 'conjunction' }).format(names)
}
