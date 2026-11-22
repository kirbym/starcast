import type { Kind } from './kind.ts'
import {
  PALETTE,
  type PaletteColor,
  SPRITE_SIZE,
  SPRITES,
  type SpriteLayer,
  TRANSPARENT,
} from './sprites.ts'

/** How many CSS pixels each sprite pixel takes: 30 × 5 = 150px, so every edge stays crisp. */
const PIXEL_SCALE = 5

/** A Highlight Card's Kind Sprite: pixel art of its kind, drawn as SVG rects layer by layer.
 * Decorative, since the card's kind label already names the kind. */
export function KindSprite({ kind }: { kind: Kind }) {
  const size = SPRITE_SIZE * PIXEL_SCALE
  return (
    <svg
      className="kind-sprite"
      data-kind={kind}
      aria-hidden="true"
      width={size}
      height={size}
      viewBox={`0 0 ${SPRITE_SIZE} ${SPRITE_SIZE}`}
      shapeRendering="crispEdges"
    >
      {SPRITES[kind].layers.map((layer) => (
        <g key={layer.name} data-layer={layer.name}>
          {runsOf(layer).map(({ x, y, width, color }) => (
            <rect key={`${x},${y}`} x={x} y={y} width={width} height={1} fill={PALETTE[color]} />
          ))}
        </g>
      ))}
    </svg>
  )
}

/** A layer's painted pixels, each row's same-colored neighbors merged into one run. */
function runsOf(layer: SpriteLayer) {
  const runs: { x: number; y: number; width: number; color: PaletteColor }[] = []
  layer.grid.forEach((row, y) => {
    let x = 0
    while (x < row.length) {
      const pixel = row[x]
      let end = x + 1
      while (row[end] === pixel) end++
      if (pixel !== TRANSPARENT) runs.push({ x, y, width: end - x, color: pixel as PaletteColor })
      x = end
    }
  })
  return runs
}
