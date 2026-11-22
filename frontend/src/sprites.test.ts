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
  TRANSPARENT,
  TURN_FRAMES,
} from './sprites.ts'

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

/** How far right of the disk's middle its lit pixels lie on average, in sprite pixels. */
function litOffset(phase: MoonPhaseName) {
  const disk = MOON_PHASE_SPRITES[phase].layers.find((layer) => layer.name === 'disk')!
  const xs = disk.grid.flatMap((row) =>
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

test('a waxing Moon is lit on its right and a waning Moon on its left', () => {
  for (const phase of ['waxing_crescent', 'first_quarter', 'waxing_gibbous'] as const) {
    expect(litOffset(phase), phase).toBeGreaterThan(1)
  }
  for (const phase of ['waning_crescent', 'last_quarter', 'waning_gibbous'] as const) {
    expect(litOffset(phase), phase).toBeLessThan(-1)
  }
})
