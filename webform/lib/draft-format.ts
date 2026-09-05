import { canonicalDestination } from './airports'

export const escapeHtml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
export function mapsUrl(place: string, destination: string) {
  const local = place.match(/\(([^()]*[A-Za-z][^()]*)\)/)?.[1]
  const name = local || place.trim()
  const suffix = local ? place.slice(place.lastIndexOf(')') + 1).trim() : ''
  const query = suffix ? `${name}${suffix}` : name.includes(',') ? name : `${name}, ${canonicalDestination(destination)}`
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`
}
export function itineraryDays(response: string) {
  const days: { label: string; places: string[]; destination?: string }[] = []
  let current: typeof days[number] | undefined
  for (const raw of response.split('\n')) {
    const line = raw.trim()
    if (/^###\s+יום\s+\d+/.test(line)) { current = { label: line.replace(/^###\s+/, ''), places: [] }; days.push(current) }
    else if (/^#{1,3}\s/.test(line)) current = undefined
    if (!current) continue
    if (line.startsWith('**מיקום ליום:** ')) current.destination = line.slice('**מיקום ליום:** '.length).trim()
    for (const match of line.matchAll(/\[\[([^\]]+)\]\]/g)) if (!current.places.includes(match[1].trim())) current.places.push(match[1].trim())
  }
  return days.filter(day => day.places.length)
}
export function routeUrl(places: string[], destination: string) {
  if (places.length === 1) return mapsUrl(places[0], destination)
  const queries = places.map(place => `${place}, ${canonicalDestination(destination)}`)
  return `https://www.google.com/maps/dir/?${new URLSearchParams({ api: '1', origin: queries[0], destination: queries.at(-1)!, ...(queries.length > 2 ? { waypoints: queries.slice(1, -1).join('|') } : {}) })}`
}
export function inlineHtml(text: string, destination: string): string {
  return text.split(/(\[\[[^\]]+\]\]|\*\*[^*]+\*\*)/g).map(part => {
    if (part.startsWith('[[') && part.endsWith(']]')) return `<a target="_blank" rel="noopener noreferrer" href="${escapeHtml(mapsUrl(part.slice(2, -2), destination))}">${escapeHtml(part.slice(2, -2))}</a>`
    if (part.startsWith('**') && part.endsWith('**')) return `<strong>${escapeHtml(part.slice(2, -2))}</strong>`
    return escapeHtml(part)
  }).join('')
}
export function draftHtml(response: string, destination: string) {
  const lines = response.split('\n'), output: string[] = []
  let currentDestination = destination
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue
    if (line.startsWith('**מיקום ליום:** ')) currentDestination = line.slice('**מיקום ליום:** '.length).trim()
    if (line.startsWith('|') && /^\|[\s:|\-]+\|$/.test(lines[i + 1]?.trim() ?? '')) {
      const cells = (s: string, tag: string) => s.trim().slice(1, -1).split('|').map(cell => `<${tag}>${inlineHtml(cell.trim(), currentDestination)}</${tag}>`).join('')
      let table = `<div class="table-scroll"><table><thead><tr>${cells(line, 'th')}</tr></thead><tbody>`
      i += 2
      while (i < lines.length && lines[i].trim().startsWith('|')) { table += `<tr>${cells(lines[i], 'td')}</tr>`; i++ }
      i--
      output.push(table + '</tbody></table></div>'); continue
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/)
    if (heading) { const tag = `h${heading[1].length}`; output.push(`<${tag}>${inlineHtml(heading[2], currentDestination)}</${tag}>`); continue }
    if (line === '---') { output.push('<hr/>'); continue }
    if (/^[-*] /.test(line)) {
      let list = '<ul>'
      while (i < lines.length && /^[-*] /.test(lines[i].trim())) { list += `<li>${inlineHtml(lines[i].trim().slice(2), currentDestination)}</li>`; i++ }
      i--; output.push(list + '</ul>'); continue
    }
    output.push(`<p>${inlineHtml(line, currentDestination)}</p>`)
  }
  return output.join('')
}
export const draftStyles = `.draft-body{direction:rtl;line-height:1.8;color:#26333b}.draft-body h1{font-size:26px}.draft-body h2{font-size:21px;border-bottom:2px solid #e8d8c5;margin-top:28px;padding-bottom:8px}.draft-body h3{font-size:18px;margin-top:22px;color:#994916}.draft-body p{margin:10px 0}.draft-body ul{list-style:disc;padding-right:24px}.draft-body a{color:#176775;text-decoration:underline}.draft-body table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px}.draft-body th,.draft-body td{padding:12px;border:1px solid #dedbd5;text-align:right;vertical-align:top}.draft-body th{background:#f7eee3}.draft-body tr:nth-child(even){background:#fafaf8}.table-scroll{overflow-x:auto}@media print{.table-scroll{overflow:visible}.draft-body h2,.draft-body h3{break-after:avoid}.draft-body tr{break-inside:avoid}}`
export function wordHtml(response: string, destination: string) {
  const links = itineraryDays(response).map(day => `<p><strong>${escapeHtml(day.label)}</strong></p><ul>${day.places.map(place => `<li><a href="${escapeHtml(mapsUrl(place, day.destination || destination))}">${escapeHtml(place)}</a></li>`).join('')}</ul>`).join('')
  return `<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8"><title>תוכנית הטיול</title><style>body{font-family:Arial}${draftStyles}</style></head><body class="draft-body"><p>תוכנית ראשונית — בכפוף לאישור סוכן נסיעות</p>${draftHtml(response, destination)}${links ? `<h2>קישורים למפה לפי ימים</h2>${links}` : ''}</body></html>`
}
