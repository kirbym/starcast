import { expect, test } from 'vitest'
import { KIND_LABELS, KINDS } from './kind.ts'
import { PALETTE, SPRITE_SIZE, SPRITES, TRANSPARENT } from './sprites.ts'

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

test.each(KINDS)("every layer of the %s sprite is a 30×30 grid of palette characters", (kind) => {
  const { layers } = SPRITES[kind]
  expect(layers.length).toBeGreaterThan(0)
  const allowed = new Set([TRANSPARENT, ...Object.keys(PALETTE)])
  for (const layer of layers) {
    expect(layer.grid, layer.name).toHaveLength(SPRITE_SIZE)
    for (const row of layer.grid) {
      expect(row, layer.name).toHaveLength(SPRITE_SIZE)
      for (const pixel of row) expect(allowed, `${layer.name}: "${pixel}"`).toContain(pixel)
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
