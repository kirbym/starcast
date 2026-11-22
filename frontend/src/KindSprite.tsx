import type { CSSProperties } from 'react'
import type { Kind } from './kind.ts'
import type { MoonPhase } from './report.ts'
import {
  framesOf,
  type Hemisphere,
  PALETTE,
  type PaletteColor,
  SPRITE_SIZE,
  type SpriteLayer,
  spriteFor,
  TRANSPARENT,
} from './sprites.ts'

/** How many CSS pixels each sprite pixel takes: 30 × 5 = 150px, so every edge stays crisp. */
const PIXEL_SCALE = 5

/** A Highlight Card's Kind Sprite: pixel art of its kind, drawn as SVG rects layer by layer.
 * Decorative, since the card's kind label already names the kind. The Moon's is drawn at its
 * phase, or full when it has none, as seen from the hemisphere. Its layers move by the classes
 * index.css gives them, and hold still under prefers-reduced-motion: reduce. */
export function KindSprite({
  kind,
  moonPhase,
  hemisphere = 'northern',
}: {
  kind: Kind
  moonPhase?: MoonPhase | null
  hemisphere?: Hemisphere
}) {
  const size = SPRITE_SIZE * PIXEL_SCALE
  const { sprite, phase } = spriteFor(kind, moonPhase, hemisphere)
  return (
    <svg
      className="kind-sprite"
      data-kind={kind}
      data-moon-phase={phase}
      data-hemisphere={phase && hemisphere}
      aria-hidden="true"
      width={size}
      height={size}
      viewBox={`0 0 ${SPRITE_SIZE} ${SPRITE_SIZE}`}
      shapeRendering="crispEdges"
    >
      {sprite.layers.map((layer) => (
        <g
          key={layer.name}
          data-layer={layer.name}
          className={layer.motion === 'twinkle' ? undefined : motionClass(layer)}
        >
          <LayerPixels layer={layer} />
        </g>
      ))}
    </svg>
  )
}

function motionClass(layer: SpriteLayer) {
  return layer.motion && `sprite-${layer.motion}`
}

/** A layer's pixels. A turning layer draws each frame in its own group, shown in turn; a
 * twinkling layer draws each star in its own group, so the stars twinkle at staggered times. */
function LayerPixels({ layer }: { layer: SpriteLayer }) {
  if (layer.frames) {
    return framesOf(layer).map((grid, index) => (
      <g
        key={index}
        data-frame={index}
        className="sprite-frame"
        style={{ '--frame': index } as CSSProperties}
      >
        <Pixels grid={grid} />
      </g>
    ))
  }
  if (layer.motion === 'twinkle') {
    return starsOf(layer.grid).map((star, index) => (
      <g
        key={index}
        data-star={index}
        className={motionClass(layer)}
        style={{ '--star': index } as CSSProperties}
      >
        <Pixels grid={star} />
      </g>
    ))
  }
  return <Pixels grid={layer.grid} />
}

function Pixels({ grid }: { grid: string[] }) {
  return runsOf(grid).map(({ x, y, width, color }) => (
    <rect key={`${x},${y}`} x={x} y={y} width={width} height={1} fill={PALETTE[color]} />
  ))
}

/** A grid's painted pixels, each row's same-colored neighbors merged into one run. */
function runsOf(grid: string[]) {
  const runs: { x: number; y: number; width: number; color: PaletteColor }[] = []
  grid.forEach((row, y) => {
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

/** A grid split into its stars: each group of painted pixels touching side or corner, as a
 * grid of its own, in the order a top-to-bottom scan first meets them. */
function starsOf(grid: string[]): string[][] {
  const starOf = grid.map((row) => Array.from(row, () => -1))
  const stars: string[][][] = []
  grid.forEach((row, y) => {
    Array.from(row).forEach((pixel, x) => {
      if (pixel === TRANSPARENT || starOf[y][x] !== -1) return
      const star = grid.map((r) => Array.from(r, () => TRANSPARENT))
      const pending = [[x, y]]
      starOf[y][x] = stars.length
      while (pending.length) {
        const [px, py] = pending.pop()!
        star[py][px] = grid[py][px]
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            const nx = px + dx
            const ny = py + dy
            if (grid[ny]?.[nx] === undefined || grid[ny][nx] === TRANSPARENT) continue
            if (starOf[ny][nx] !== -1) continue
            starOf[ny][nx] = stars.length
            pending.push([nx, ny])
          }
        }
      }
      stars.push(star)
    })
  })
  return stars.map((star) => star.map((row) => row.join('')))
}
