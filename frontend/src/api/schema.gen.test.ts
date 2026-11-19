// @vitest-environment node
import { readFileSync } from 'node:fs'
import openapiTS, { astToString, COMMENT_HEADER } from 'openapi-typescript'
import { expect, test } from 'vitest'

const lf = (text: string) => text.replace(/\r\n/g, '\n')

// The frontend's API types are generated from the backend's OpenAPI document. If this fails, run
// `npm run gen:api` (and, if the backend changed, `uv run scripts/export_openapi.py` first).
test('the generated API types match the committed OpenAPI document', async () => {
  const document = new URL('./openapi.json', import.meta.url)
  const generated = COMMENT_HEADER + astToString(await openapiTS(document))

  const committed = readFileSync(new URL('./schema.gen.ts', import.meta.url), 'utf8')

  expect(lf(committed)).toBe(lf(generated))
})
