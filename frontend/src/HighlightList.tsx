import { useId, useLayoutEffect, useRef, useState } from 'react'
import { LocalTime, PositionalFields } from './PositionalFields.tsx'
import type { HighlightCard, SignificantEvent } from './report.ts'

export function HighlightList({ highlights }: { highlights: HighlightCard[] }) {
  const listRef = useTallestSummary(highlights)
  return (
    <section className="highlights" ref={listRef}>
      {highlights.map((highlight) => (
        <Card key={highlight.id} highlight={highlight} />
      ))}
    </section>
  )
}

/** Keeps `--tallest-summary` on the list at the height of its tallest Highlight Card summary.
 * Side by side, index.css makes every card at least that tall: closed cards match, and an
 * expanded one grows past them without changing theirs. */
function useTallestSummary(highlights: HighlightCard[]) {
  const listRef = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const list = listRef.current
    if (!list) return
    const summaries = Array.from(list.querySelectorAll<HTMLElement>('.highlight-card-summary'))
    const observer = new ResizeObserver(() => {
      const tallest = Math.max(...summaries.map((summary) => summary.offsetHeight))
      list.style.setProperty('--tallest-summary', `${tallest}px`)
    })
    for (const summary of summaries) observer.observe(summary)
    return () => observer.disconnect()
  }, [highlights])
  return listRef
}

/** A Highlight Card: its summary (title, paragraph and Details toggle), then its Detail Layer
 * while expanded. */
function Card({ highlight }: { highlight: HighlightCard }) {
  const [expanded, setExpanded] = useState(false)
  const headingId = useId()
  const toggleId = useId()
  const regionId = useId()
  return (
    <article className="highlight-card" aria-labelledby={headingId}>
      <div className="highlight-card-summary">
        <h2 id={headingId}>
          {highlight.mini_headline} <span className="highlight-kind">{kindLabel(highlight)}</span>
        </h2>
        <p>{highlight.paragraph}</p>
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
      </div>
      {expanded && (
        <section id={regionId} className="detail-layer" aria-labelledby={toggleId}>
          <dl>
            {highlight.event && <EventFields event={highlight.event} />}
            <PositionalFields body={highlight} />
          </dl>
        </section>
      )}
    </article>
  )
}

/** What kind of Visible body a Highlight Card describes, as its title's closing label: the
 * event's own kind for a Significant Event, so every Highlight Card says exactly what it is. */
function kindLabel(highlight: HighlightCard): string {
  if (highlight.object_type === 'significant_event' && highlight.event) {
    return EVENT_LABELS[highlight.event.event_type].name
  }
  if (highlight.object_type === 'dso' && highlight.dso_type) {
    return DSO_TYPE_LABELS[highlight.dso_type]
  }
  return KIND_LABELS[highlight.object_type]
}

/** How a DSO Highlight Card's title labels each DSO type. */
const DSO_TYPE_LABELS: Record<NonNullable<HighlightCard['dso_type']>, string> = {
  galaxy: 'Galaxy',
  nebula: 'Nebula',
  globular_cluster: 'Globular Cluster',
  open_cluster: 'Open Cluster',
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
