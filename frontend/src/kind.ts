import type { HighlightCard } from './report.ts'

type ObjectType = HighlightCard['object_type']
type DsoType = NonNullable<HighlightCard['dso_type']>
type EventType = NonNullable<HighlightCard['event']>['event_type']

/** What a Highlight Card describes, as its kind label and Kind Sprite show it: its object type,
 * except that a DSO is its DSO type and a Significant Event is its event type. */
export type Kind = Exclude<ObjectType, 'dso' | 'significant_event'> | DsoType | EventType

/** How a Highlight Card's title labels each kind. KINDS lists the kinds in this order. */
export const KIND_LABELS: Record<Kind, string> = {
  planet: 'Planet',
  moon: 'Moon',
  constellation: 'Constellation',
  bright_star: 'Bright Star',
  named_comet: 'Comet',
  galaxy: 'Galaxy',
  nebula: 'Nebula',
  globular_cluster: 'Globular Cluster',
  open_cluster: 'Open Cluster',
  conjunction: 'Conjunction',
  opposition: 'Opposition',
  meteor_shower: 'Meteor Shower',
}

export const KINDS = Object.keys(KIND_LABELS) as Kind[]

/** A Highlight Card's kind, or null for a DSO without a DSO type or a Significant Event without
 * its event, which the backend never sends. */
export function kindOf(highlight: HighlightCard): Kind | null {
  switch (highlight.object_type) {
    case 'dso':
      return highlight.dso_type ?? null
    case 'significant_event':
      return highlight.event?.event_type ?? null
    default:
      return highlight.object_type
  }
}

/** The closing label of a Highlight Card's title, so every Highlight Card says exactly what it
 * is. The fallbacks name a kindless DSO or Significant Event. */
export function kindLabel(highlight: HighlightCard): string {
  const kind = kindOf(highlight)
  if (kind) return KIND_LABELS[kind]
  return highlight.object_type === 'dso' ? 'Deep-Sky Object' : 'Event'
}
