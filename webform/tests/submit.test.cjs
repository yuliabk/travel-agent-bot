const assert = require('node:assert/strict')
const { readFileSync } = require('node:fs')
const { resolve } = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(path, globals = {}) {
  const exports = {}
  const code = ts.transpileModule(readFileSync(resolve(__dirname, '..', path), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  vm.runInNewContext(code, { exports, Response, AbortController, TextEncoder, ReadableStream, setTimeout, clearTimeout, console, ...globals })
  return exports
}

async function main() {
  const airports = load('lib/airports.ts')
  const calls = []
  const route = load('app/api/submit/route.ts', {
    process: { env: { TRAVEL_AGENT_API_URL: 'https://backend.example', TRAVEL_AGENT_WEB_TOKEN: 'test-token' } },
    require: (name) => name === '@/lib/airports' ? airports : {},
    fetch: async (url, options) => {
      calls.push({ url, options })
      return Response.json({ status: 'AI_DRAFT', rendered_draft: 'טיוטת בדיקה', proposal: {} })
    },
  })
  const body = { name: 'Test', email: 'test@example.com', origin: 'Tel Aviv', destination: 'Rome',
    dateFrom: '2026-10-10', dateTo: '2026-10-13', budgetAmount: '5000', consent: true,
    originAirport: ' tlv ', destinationAirport: 'רומא — פיומיצ׳ינו (FCO)' }
  const submit = (value) => route.POST({ json: async () => value })
  const response = await submit(body)
  assert.equal(response.status, 200)
  assert.match(await response.text(), /AI_DRAFT/)
  assert.equal(calls.length, 1)
  const backend = JSON.parse(calls[0].options.body)
  assert.equal(backend.origin_iata, 'TLV')
  assert.equal(backend.destination_iata, 'FCO')
  assert.equal(backend.completion.origin, 'Tel Aviv')
  assert.equal(backend.payload.destination, 'Rome')
  for (const destinationAirport of ['', 'יוון', 'TLV', '123']) {
    const rejected = await submit({ ...body, destinationAirport })
    assert.equal(rejected.status, 422)
  }
  assert.equal(calls.length, 1, 'invalid airports must never call the backend')
  console.log('Submit regression tests passed')
}
main().catch((error) => { console.error(error); process.exitCode = 1 })

