import { useId, useLayoutEffect, useRef, useState } from 'react'
import { KindSprite } from './KindSprite.tsx'
import { KIND_LABELS, kindLabel, kindOf } from './kind.ts'
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

/** A Highlight Card: its summary (Kind Sprite, title, paragraph and Details toggle), then its
 * Detail Layer while expanded. */
function Card({ highlight }: { highlight: HighlightCard }) {
  const [expanded, setExpanded] = useState(false)
  const kind = kindOf(highlight)
  const headingId = useId()
  const toggleId = useId()
  const regionId = useId()
  return (
    <article className="highlight-card" aria-labelledby={headingId}>
      <div className="highlight-card-summary">
        {kind && <KindSprite kind={kind} />}
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

/** What a Significant Event is, what it involves, and when it peaks. */
function EventFields({ event }: { event: SignificantEvent }) {
  return (
    <>
      <dt>Event</dt>
      <dd>{KIND_LABELS[event.event_type]}</dd>
      {event.related_object_names && (
        <>
          <dt>{EVENT_BODIES_LABELS[event.event_type]}</dt>
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

/** What the Detail Layer calls the bodies each event type involves. */
const EVENT_BODIES_LABELS: Record<SignificantEvent['event_type'], string> = {
  conjunction: 'Bodies',
  opposition: 'Planet',
  meteor_shower: 'Radiant',
}

/** "Jupiter and Saturn", or "Mars, Jupiter and Saturn". */
function joinNames(names: string[]): string {
  return new Intl.ListFormat('en', { type: 'conjunction' }).format(names)
}
