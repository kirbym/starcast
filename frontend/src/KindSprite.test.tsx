import { render } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import css from './index.css?raw'
import { KINDS } from './kind.ts'
import { KindSprite } from './KindSprite.tsx'

type MotionPreference = 'no-preference' | 'reduce'

/** Applies index.css as a viewer with this prefers-reduced-motion setting sees it. jsdom skips
 * @media rules, so the matching blocks are unwrapped into plain rules and the rest dropped. */
function applyStylesheet(preference: MotionPreference) {
  const parsed = document.createElement('style')
  parsed.textContent = css
  document.head.append(parsed)
  const rules = Array.from(parsed.sheet!.cssRules).flatMap((rule) => {
    if (!(rule instanceof CSSMediaRule)) return [rule.cssText]
    const matches = rule.conditionText.replaceAll(' ', '') === `(prefers-reduced-motion:${preference})`
    return matches ? Array.from(rule.cssRules, (inner) => inner.cssText) : []
  })
  parsed.remove()
  const applied = document.createElement('style')
  applied.textContent = rules.join('\n')
  document.head.append(applied)
}

afterEach(() => {
  document.head.querySelectorAll('style').forEach((style) => style.remove())
})

/** Every element of the sprite, the <svg> included, with the name and timing function of the
 * animation it runs. jsdom keeps the `animation` shorthand whole, so they are read from it. */
function animationsOf(sprite: Element) {
  const names = new Set(keyframesRules().keys())
  return [sprite, ...sprite.querySelectorAll('*')].map((element) => {
    const tokens = getComputedStyle(element).animation.split(/\s+/)
    return {
      element,
      name: tokens.find((token) => names.has(token)) ?? 'none',
      timing: tokens.find((token) => /^(ease|linear|step)/.test(token)) ?? 'ease',
    }
  })
}

const isAnimated = (name: string) => name !== 'none'

/** The keyframes rules index.css declares, by name. */
function keyframesRules() {
  const parsed = document.createElement('style')
  parsed.textContent = css
  document.head.append(parsed)
  const keyframes = Array.from(parsed.sheet!.cssRules).filter(
    (rule): rule is CSSKeyframesRule => rule instanceof CSSKeyframesRule,
  )
  parsed.remove()
  return new Map(keyframes.map((rule) => [rule.name, rule]))
}

test.each(KINDS)('the %s sprite animates when motion is allowed', (kind) => {
  applyStylesheet('no-preference')
  const { container } = render(<KindSprite kind={kind} />)
  const animated = animationsOf(container.querySelector('svg')!).filter(({ name }) =>
    isAnimated(name),
  )
  expect(animated.length).toBeGreaterThan(0)
  const keyframes = keyframesRules()
  for (const { name } of animated) expect(keyframes.has(name), name).toBe(true)
})

test.each(KINDS)('the %s sprite holds still under prefers-reduced-motion: reduce', (kind) => {
  applyStylesheet('reduce')
  const { container } = render(<KindSprite kind={kind} />)
  for (const { element, name } of animationsOf(container.querySelector('svg')!)) {
    expect(isAnimated(name), `${element.tagName} ${element.getAttribute('class')}: ${name}`).toBe(
      false,
    )
  }
})

test.each(KINDS)('the still %s sprite shows each turning layer at its first frame', (kind) => {
  applyStylesheet('reduce')
  const { container } = render(<KindSprite kind={kind} />)
  for (const layer of container.querySelectorAll('[data-layer]')) {
    const frames = layer.querySelectorAll(':scope > [data-frame]')
    frames.forEach((frame, index) => {
      expect(getComputedStyle(frame).opacity, `${layer.getAttribute('data-layer')} ${index}`).toBe(
        index === 0 ? '1' : '0',
      )
    })
  }
})

test('the planet and galaxy sprites turn by swapping four frames', () => {
  for (const kind of ['planet', 'galaxy'] as const) {
    const { container } = render(<KindSprite kind={kind} />)
    const turning = container.querySelector('[data-layer] > [data-frame]')!.parentElement!
    expect(turning.querySelectorAll(':scope > [data-frame]')).toHaveLength(4)
  }
})

test('the twinkling sprites stagger their stars', () => {
  applyStylesheet('no-preference')
  for (const kind of ['constellation', 'open_cluster', 'globular_cluster'] as const) {
    const { container } = render(<KindSprite kind={kind} />)
    const stars = [...container.querySelectorAll('[data-star]')]
    expect(stars.length, kind).toBeGreaterThan(3)
    // jsdom leaves var() unresolved, so check each star's delay comes from its own offset.
    const offsets = new Set(stars.map((star) => getComputedStyle(star).getPropertyValue('--star')))
    expect(offsets.size, kind).toBe(stars.length)
    for (const star of stars) expect(getComputedStyle(star).animationDelay).toContain('var(--star)')
  }
})

test('sprite motion moves only by whole pixels, in steps, and never rotates or scales', () => {
  for (const [name, rule] of keyframesRules()) {
    if (!name.startsWith('sprite-')) continue
    const transforms = Array.from(rule.cssRules as CSSRuleList, (frame) =>
      (frame as CSSKeyframeRule).style.transform,
    ).filter(Boolean)
    for (const transform of transforms) {
      expect(transform, name).toMatch(/^(none|translate\(-?\d+px(, -?\d+px)?\))$/)
    }
  }
  applyStylesheet('no-preference')
  const moving = keyframesRules()
  for (const kind of KINDS) {
    const { container, unmount } = render(<KindSprite kind={kind} />)
    for (const { name, timing } of animationsOf(container.querySelector('svg')!)) {
      const rule = moving.get(name)
      if (!rule || !rule.cssText.includes('transform')) continue
      expect(timing, `${kind} ${name}`).toBe('step-end')
    }
    unmount()
  }
})
