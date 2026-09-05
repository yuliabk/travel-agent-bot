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
  assert.equal(backend.payload.destination, 'Rome, Italy')
  const automatic = await submit({ ...body, destinationAirport: '' })
  assert.equal(automatic.status, 200)
  assert.equal(JSON.parse(calls.at(-1).options.body).destination_iata, 'FCO')
  const changedDestination = await submit({ ...body, destination: 'פריז' })
  assert.equal(changedDestination.status, 200)
  assert.equal(JSON.parse(calls.at(-1).options.body).destination_iata, 'CDG', 'stale Rome airport must not survive a destination change')
  const alternative = await submit({ ...body, destination: 'Paris', destinationAirport: 'ORY' })
  assert.equal(alternative.status, 200)
  assert.equal(JSON.parse(calls.at(-1).options.body).destination_iata, 'ORY')
  assert.equal(airports.destinationAirportCode('  ROME  '), 'FCO')
  assert.equal(airports.destinationAirportCode('יוון'), null)
  assert.equal(airports.destinationAirportCode('יוון', 'JTR'), 'JTR')
  assert.equal(airports.destinationAirportCode('Paris, Texas'), null)
  for (const destination of ['וורצלוב פולין', 'ורוצלב', 'וורוצלב, פולין', 'Wrocław, Poland', '  WROCLAW (POLAND)  ', 'פולין — ורוצלב']) {
    assert.equal(airports.destinationAirportCode(destination), 'WRO', destination)
    const resolved = await submit({ ...body, destination, destinationAirport: '' })
    assert.equal(resolved.status, 200)
    assert.equal(JSON.parse(calls.at(-1).options.body).destination_iata, 'WRO')
  }
  assert.equal(airports.canonicalDestination('פולין ,וורצלוב'), 'Wroclaw, Poland')
  assert.equal(airports.canonicalDestination('Paris, Texas'), 'Paris, Texas')
  assert.equal(airports.destinationAirportCode('פולין'), null)
  assert.equal(airports.destinationAirportCode('Wroclaw Germany'), null)
  assert.equal(airports.destinationAirportCode('וורצלוב פולין', 'FCO'), 'WRO')
  for (const destinationAirport of ['', 'יוון', 'TLV', '123']) {
    const rejected = await submit({ ...body, destination: 'Unknown destination', destinationAirport })
    assert.equal(rejected.status, 422)
  }
  assert.equal(calls.length, 10, 'invalid airports must never call the backend')
  console.log('Submit regression tests passed')
}
main().catch((error) => { console.error(error); process.exitCode = 1 })
