import { expect, test } from 'vitest'
import { KIND_LABELS, KINDS } from './kind.ts'
import { framesOf, PALETTE, SPRITE_SIZE, SPRITES, TRANSPARENT, TURN_FRAMES } from './sprites.ts'

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
