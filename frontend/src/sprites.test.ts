import { expect, test } from 'vitest'
import { KIND_LABELS, KINDS } from './kind.ts'
import {
  framesOf,
  MOON_PHASE_SPRITES,
  MOON_PHASES,
  type MoonPhaseName,
  moonPhaseName,
  PALETTE,
  SPRITE_SIZE,
  SPRITES,
  spriteFor,
  TRANSPARENT,
  TURN_FRAMES,
} from './sprites.ts'
import type { MoonPhase } from './report.ts'

test('there is one sprite for each of the twelve kinds', () => {
  expect(KINDS).toEqual([
    'planet',
    'moon',
    'constellation',
    'bright_star',
    'named_comet',
    'galaxy',
    'nebula',
    'globular_cluster',
    'open_cluster',
    'conjunction',
    'opposition',
    'meteor_shower',
  ])
  expect(Object.keys(SPRITES).sort()).toEqual([...KINDS].sort())
  expect(Object.keys(KIND_LABELS).sort()).toEqual([...KINDS].sort())
})

test.each(KINDS)("every frame of the %s sprite is a 30×30 grid of palette characters", (kind) => {
  const { layers } = SPRITES[kind]
  expect(layers.length).toBeGreaterThan(0)
  const allowed = new Set([TRANSPARENT, ...Object.keys(PALETTE)])
  for (const layer of layers) {
    for (const [index, grid] of framesOf(layer).entries()) {
      const label = `${layer.name} frame ${index}`
      expect(grid, label).toHaveLength(SPRITE_SIZE)
      for (const row of grid) {
        expect(row, label).toHaveLength(SPRITE_SIZE)
        for (const pixel of row) expect(allowed, `${label}: "${pixel}"`).toContain(pixel)
      }
    }
  }
})

test.each(KINDS)('every frame of the %s sprite differs from the one before it', (kind) => {
  for (const layer of SPRITES[kind].layers) {
    const frames = framesOf(layer)
    frames.slice(1).forEach((grid, index) => {
      expect(grid.join(''), `${layer.name} frame ${index + 1}`).not.toBe(frames[index].join(''))
    })
  }
})

test('the turning layers each have four frames', () => {
  const turning = KINDS.flatMap((kind) =>
    SPRITES[kind].layers.filter((layer) => layer.frames).map((layer) => `${kind} ${layer.name}`),
  )
  expect(turning).toEqual(['planet disk', 'galaxy arms'])
  for (const kind of KINDS) {
    for (const layer of SPRITES[kind].layers) {
      if (layer.frames) expect(framesOf(layer), layer.name).toHaveLength(TURN_FRAMES)
    }
  }
})

test.each(KINDS)('the %s sprite paints something and names its layers uniquely', (kind) => {
  const { layers } = SPRITES[kind]
  expect(new Set(layers.map((layer) => layer.name)).size).toBe(layers.length)
  for (const layer of layers) {
    expect(layer.grid.join('').replaceAll(TRANSPARENT, ''), layer.name).not.toBe('')
  }
})

test('the shared palette has about a dozen colors', () => {
  const colors = Object.values(PALETTE)
  expect(colors.length).toBeGreaterThanOrEqual(10)
  expect(colors.length).toBeLessThanOrEqual(14)
  for (const color of colors) expect(color).toMatch(/^#[0-9a-f]{6}$/)
})

const litPixels = (phase: MoonPhaseName) =>
  MOON_PHASE_SPRITES[phase].layers
    .filter((layer) => layer.name === 'disk')
    .flatMap((layer) => layer.grid.join('').replaceAll(TRANSPARENT, '').split(''))

/** How far right of the disk's middle a northern-hemisphere Moon's lit pixels lie on average. */
function litOffset(phase: MoonPhaseName) {
  return litOffsetOf(MOON_PHASE_SPRITES[phase].layers.find((layer) => layer.name === 'disk')!.grid)
}

/** How far right of the grid's middle its painted pixels lie on average, in sprite pixels. */
function litOffsetOf(grid: string[]) {
  const xs = grid.flatMap((row) =>
    Array.from(row).flatMap((pixel, x) => (pixel === TRANSPARENT ? [] : [x + 0.5])),
  )
  return xs.reduce((sum, x) => sum + x, 0) / xs.length - SPRITE_SIZE / 2
}

test.each([
  [0.0, true, 'new'],
  [0.02, false, 'new'],
  [0.15, true, 'waxing_crescent'],
  [0.15, false, 'waning_crescent'],
  [0.5, true, 'first_quarter'],
  [0.5, false, 'last_quarter'],
  [0.82, true, 'waxing_gibbous'],
  [0.82, false, 'waning_gibbous'],
  [0.99, true, 'full'],
  [1.0, false, 'full'],
] as const)('a Moon %s lit and waxing=%s is drawn as %s', (fraction, waxing, phase) => {
  expect(moonPhaseName({ illuminated_fraction: fraction, waxing })).toBe(phase)
})

test('the Moon has one sprite for each of its eight phases', () => {
  expect(MOON_PHASES).toEqual([
    'new',
    'waxing_crescent',
    'first_quarter',
    'waxing_gibbous',
    'full',
    'waning_gibbous',
    'last_quarter',
    'waning_crescent',
  ])
  expect(Object.keys(MOON_PHASE_SPRITES).sort()).toEqual([...MOON_PHASES].sort())
})

test.each(MOON_PHASES)('the %s Moon is a 30×30 palette grid that keeps its pulsing halo', (phase) => {
  const { layers } = MOON_PHASE_SPRITES[phase]
  const allowed = new Set([TRANSPARENT, ...Object.keys(PALETTE)])
  for (const layer of layers) {
    expect(layer.grid, layer.name).toHaveLength(SPRITE_SIZE)
    for (const row of layer.grid) {
      expect(row, layer.name).toHaveLength(SPRITE_SIZE)
      for (const pixel of row) expect(allowed).toContain(pixel)
    }
    expect(layer.grid.join('').replaceAll(TRANSPARENT, ''), layer.name).not.toBe('')
  }
  expect(layers[0]).toMatchObject({ name: 'halo', motion: 'pulse' })
})

test('the Moon grows from new to full and shrinks back', () => {
  expect(litPixels('new')).toHaveLength(0)
  const waxing = ['waxing_crescent', 'first_quarter', 'waxing_gibbous', 'full'] as const
  const waning = ['full', 'waning_gibbous', 'last_quarter', 'waning_crescent'] as const
  waxing.slice(1).forEach((phase, index) => {
    expect(litPixels(phase).length, phase).toBeGreaterThan(litPixels(waxing[index]).length)
  })
  waning.slice(1).forEach((phase, index) => {
    expect(litPixels(phase).length, phase).toBeLessThan(litPixels(waning[index]).length)
  })
})

/** A Moon phase the backend might send, for each phase it is drawn as. */
const SAMPLE_PHASE: Record<MoonPhaseName, MoonPhase> = {
  new: { illuminated_fraction: 0.01, waxing: true },
  waxing_crescent: { illuminated_fraction: 0.2, waxing: true },
  first_quarter: { illuminated_fraction: 0.52, waxing: true },
  waxing_gibbous: { illuminated_fraction: 0.8, waxing: true },
  full: { illuminated_fraction: 0.99, waxing: false },
  waning_gibbous: { illuminated_fraction: 0.8, waxing: false },
  last_quarter: { illuminated_fraction: 0.48, waxing: false },
  waning_crescent: { illuminated_fraction: 0.2, waxing: false },
}

test.each(MOON_PHASES)('from the southern hemisphere the %s Moon is turned halfway round', (phase) => {
  const north = spriteFor('moon', SAMPLE_PHASE[phase], 'northern')
  const south = spriteFor('moon', SAMPLE_PHASE[phase], 'southern')
  expect(north).toEqual({ sprite: MOON_PHASE_SPRITES[phase], phase })
  expect(south.phase).toBe(phase)
  expect(south.sprite.layers).toHaveLength(north.sprite.layers.length)
  south.sprite.layers.forEach((layer, index) => {
    const original = north.sprite.layers[index]
    const turned = original.grid.map((row) => [...row].reverse().join('')).reverse()
    expect(layer, layer.name).toEqual({ ...original, grid: turned })
  })
})

test('from the southern hemisphere a waxing Moon is lit on its left', () => {
  const offset = (phase: MoonPhaseName) => {
    const { layers } = spriteFor('moon', SAMPLE_PHASE[phase], 'southern').sprite
    return litOffsetOf(layers.find((layer) => layer.name === 'disk')!.grid)
  }
  expect(offset('waxing_crescent')).toBeLessThan(-1)
  expect(offset('waning_crescent')).toBeGreaterThan(1)
})

test('only the Moon turns with the hemisphere', () => {
  expect(spriteFor('planet', null, 'southern')).toEqual({ sprite: SPRITES.planet })
})

test('a waxing Moon is lit on its right and a waning Moon on its left', () => {
  for (const phase of ['waxing_crescent', 'first_quarter', 'waxing_gibbous'] as const) {
    expect(litOffset(phase), phase).toBeGreaterThan(1)
  }
  for (const phase of ['waning_crescent', 'last_quarter', 'waning_gibbous'] as const) {
    expect(litOffset(phase), phase).toBeLessThan(-1)
  }
})
