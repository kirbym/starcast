import { useId } from 'react'

export type Highlight = {
  id: string
  name: string
  mini_headline: string
  paragraph: string
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
    </article>
  )
}
