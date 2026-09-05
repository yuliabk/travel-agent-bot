const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
function load(file, extra = {}) {
  const exports = {}
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '..', file), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, { exports, URLSearchParams, AbortSignal, ...extra })
  return exports
}
const airports = load('lib/airports.ts')
const format = load('lib/draft-format.ts', { require: () => airports })
const sample = '# תוכנית\n**יעד:** ורוצלב\n| מלון | מחיר |\n| --- | --- |\n| A & B | 600 ₪ |\n### יום 1: מרכז העיר\n- [[Rynek]]\n- [[Hydropolis]]\n<script>alert(1)</script>'
const html = format.wordHtml(sample, 'פולין ,וורצלוב')
assert.ok(html.includes('<table>') && html.includes('<h3>יום 1'))
assert.ok(html.includes('<strong>יעד:</strong>'))
assert.ok(!html.includes('<script>') && html.includes('&lt;script&gt;'))
assert.ok(!html.includes('**') && !html.includes('###'))
const days = format.itineraryDays(sample)
assert.equal(days.length, 1)
assert.equal(days[0].places.length, 2)
assert.ok(decodeURIComponent(format.mapsUrl('Rynek', 'פולין ,וורצלוב')).includes('Wroclaw, Poland'))
assert.ok(new URL(format.routeUrl(days[0].places, 'ורוצלב')).searchParams.get('destination').includes('Hydropolis'))
async function main() {
  let call
  const geo = load('lib/geocoding.ts', { require: () => airports, process: { env: { TRAVEL_AGENT_API_URL: 'https://backend.example', TRAVEL_AGENT_WEB_TOKEN: 'fixture' } }, fetch: async (url, options) => { call = { url, options }; return { ok: true, json: async () => ({ points: [{ name: 'Rynek', lat: 51.1, lng: 17.03 }, { name: 'Missing', lat: 999, lng: 17 }] }) } } })
  const points = await geo.geocodePlaces(['Rynek', 'Missing'], 'פולין ,וורצלוב')
  assert.equal(points.length, 1)
  assert.equal(call.url, 'https://backend.example/v1/web/map-points')
  assert.equal(call.options.headers.Authorization, 'Bearer fixture')
  assert.equal(JSON.parse(call.options.body).destination, 'Wroclaw, Poland')
  assert.ok(geo.buildKmlByDays([{ label: 'יום 1', points }], 'טיול').includes('<coordinates>17.03,51.1,0</coordinates>'))
  console.log('Customer display, Word, map links and proxy tests passed')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
