// Suggestions are explicit airports, never an implicit choice for a country.
export const airports = [
  ['TLV', 'תל אביב — בן גוריון'], ['ETM', 'אילת — רמון'],
  ['ATH', 'אתונה'], ['JTR', 'סנטוריני'], ['HER', 'כרתים — הרקליון'],
  ['RHO', 'רודוס'], ['CDG', 'פריז — שארל דה גול'], ['ORY', 'פריז — אורלי'],
  ['FCO', 'רומא — פיומיצ׳ינו'], ['MXP', 'מילאנו — מלפנסה'],
  ['BCN', 'ברצלונה'], ['MAD', 'מדריד'], ['LHR', 'לונדון — הית׳רו'],
  ['LGW', 'לונדון — גטוויק'], ['JFK', 'ניו יורק — קנדי'],
  ['EWR', 'ניוארק'], ['AMS', 'אמסטרדם'], ['DPS', 'באלי — דנפסאר'],
  ['MLE', 'מאלה — מלדיבים'], ['HND', 'טוקיו — האנדה'],
  ['NRT', 'טוקיו — נריטה'], ['DXB', 'דובאי'], ['KEF', 'קפלאוויק — איסלנד'],
  ['ZAG', 'זאגרב'], ['DBV', 'דוברובניק'], ['PRG', 'פראג'],
  ['CUN', 'קנקון'], ['BKK', 'בנגקוק'], ['HKT', 'פוקט'],
  ['LCA', 'לרנקה'], ['PFO', 'פאפוס'], ['VIE', 'וינה'], ['BUD', 'בודפשט'],
  ['WRO', 'ורוצלב — קופרניקוס'],
  ['WAW', 'ורשה — שופן'], ['KRK', 'קרקוב'], ['POZ', 'פוזנן'], ['KTW', 'קטוביץ'],
  ['BER', 'ברלין — ברנדנבורג'], ['CIA', 'רומא — צ׳יאמפינו'], ['BGY', 'ברגמו'], ['LIN', 'מילאנו — לינאטה'], ['STN', 'לונדון — סטנסטד'],
] as const

export function airportCode(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toUpperCase()
  if (/^[A-Z]{3}$/.test(normalized)) return normalized
  const airport = airports.find(([code, label]) => `${label} (${code})`.toUpperCase() === normalized)
  return airport?.[0] ?? null
}

type Destination = { names: string[]; codes: string[]; automatic: boolean; countries?: string[] }
const destinations: Destination[] = [
  { names: ['קרקוב', 'קראקוב', 'krakow', 'cracow'], countries: ['פולין', 'poland'], codes: ['KRK'], automatic: true },
  { names: ['ורשה', 'וורשה', 'warsaw', 'warszawa'], countries: ['פולין', 'poland'], codes: ['WAW'], automatic: true },
  { names: ['פוזנן', 'פוזנאן', 'poznan'], countries: ['פולין', 'poland'], codes: ['POZ'], automatic: true },
  { names: ['קטוביץ', 'קטוביצה', 'katowice'], countries: ['פולין', 'poland'], codes: ['KTW'], automatic: true },
  { names: ['ברלין', 'berlin'], countries: ['גרמניה', 'germany'], codes: ['BER'], automatic: true },
  { names: ['ורוצלב', 'וורוצלב', 'ורוצלאב', 'וורוצלאב', 'וורצלוב', 'ורצלוב', 'ורוצלוב', 'וורוצלוב', 'וורצלב', 'wroclaw', 'breslau'], countries: ['פולין', 'poland', 'polska'], codes: ['WRO'], automatic: true },
  { names: ['רומא', 'rome', 'roma'], codes: ['FCO'], automatic: true },
  { names: ['פריז', 'paris'], codes: ['CDG', 'ORY'], automatic: true },
  { names: ['לונדון', 'london'], codes: ['LHR', 'LGW'], automatic: true },
  { names: ['ניו יורק', 'new york', 'nyc'], codes: ['JFK', 'EWR'], automatic: true },
  { names: ['טוקיו', 'tokyo'], codes: ['HND', 'NRT'], automatic: true },
  { names: ['אתונה', 'athens'], codes: ['ATH'], automatic: true },
  { names: ['סנטוריני', 'santorini'], codes: ['JTR'], automatic: true },
  { names: ['הרקליון', 'heraklion'], codes: ['HER'], automatic: true },
  { names: ['רודוס', 'rhodes'], codes: ['RHO'], automatic: true },
  { names: ['מילאנו', 'milan', 'milano'], codes: ['MXP'], automatic: true },
  { names: ['ברצלונה', 'barcelona'], codes: ['BCN'], automatic: true },
  { names: ['מדריד', 'madrid'], codes: ['MAD'], automatic: true },
  { names: ['אמסטרדם', 'amsterdam'], codes: ['AMS'], automatic: true },
  { names: ['באלי', 'bali', 'דנפסאר', 'denpasar'], codes: ['DPS'], automatic: true },
  { names: ['מלדיבים', 'האיים המלדיביים', 'maldives', 'מאלה', 'male'], codes: ['MLE'], automatic: true },
  { names: ['דובאי', 'dubai'], codes: ['DXB'], automatic: true },
  { names: ['קפלאוויק', 'keflavik', 'רייקיאוויק', 'reykjavik'], codes: ['KEF'], automatic: true },
  { names: ['זאגרב', 'zagreb'], codes: ['ZAG'], automatic: true },
  { names: ['דוברובניק', 'dubrovnik'], codes: ['DBV'], automatic: true },
  { names: ['פראג', 'prague', 'praha'], codes: ['PRG'], automatic: true },
  { names: ['קנקון', 'cancun'], codes: ['CUN'], automatic: true },
  { names: ['בנגקוק', 'bangkok'], codes: ['BKK'], automatic: true },
  { names: ['פוקט', 'phuket'], codes: ['HKT'], automatic: true },
  { names: ['לרנקה', 'larnaca'], codes: ['LCA'], automatic: true },
  { names: ['פאפוס', 'paphos'], codes: ['PFO'], automatic: true },
  { names: ['וינה', 'vienna'], codes: ['VIE'], automatic: true },
  { names: ['בודפשט', 'budapest'], codes: ['BUD'], automatic: true },
  { names: ['תל אביב', 'tel aviv'], codes: ['TLV'], automatic: true },
  { names: ['אילת', 'eilat'], codes: ['ETM'], automatic: true },
  { names: ['יוון', 'greece'], codes: ['ATH', 'JTR', 'HER', 'RHO'], automatic: false },
  { names: ['קרואטיה', 'croatia'], codes: ['ZAG', 'DBV'], automatic: false },
  { names: ['קפריסין', 'cyprus'], codes: ['LCA', 'PFO'], automatic: false },
]

const normalizeDestination = (value: string) => value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l').replace(/[,()–—-]/g, ' ').replace(/\s+/g, ' ').trim()

export function destinationMatch(value: unknown): Destination | undefined {
  if (typeof value !== 'string') return undefined
  const normalized = normalizeDestination(value)
  return destinations.find((destination) => destination.names.some((name) =>
    name === normalized || destination.countries?.some((country) =>
      normalized === `${name} ${country}` || normalized === `${country} ${name}`
    )
  ))
}

export function destinationAirportCode(destination: unknown, selected?: unknown, manual = false): string | null {
  const match = destinationMatch(destination)
  const explicit = airportCode(selected)
  if (manual) return explicit
  if (!match) return explicit
  if (explicit && match.codes.includes(explicit)) return explicit
  return match.automatic ? match.codes[0] : null
}

export function airportLabel(code: string): string {
  const entry = airports.find(([iata]) => iata === code)
  return entry ? `${entry[1]} (${code})` : code
}

// Normalize recognized city aliases only; an airport may serve a different destination.
export function canonicalDestination(value: string): string {
  const match = destinationMatch(value)
  if (!match?.automatic) return value.trim()
  const cities: Record<string, string> = {
    KRK: 'Krakow, Poland', WAW: 'Warsaw, Poland', POZ: 'Poznan, Poland', KTW: 'Katowice, Poland', BER: 'Berlin, Germany',
    WRO: 'Wroclaw, Poland', FCO: 'Rome, Italy', CDG: 'Paris, France',
    LHR: 'London, United Kingdom', JFK: 'New York, USA', HND: 'Tokyo, Japan',
    ATH: 'Athens, Greece', JTR: 'Santorini, Greece', HER: 'Heraklion, Greece',
    RHO: 'Rhodes, Greece', MXP: 'Milan, Italy', BCN: 'Barcelona, Spain', MAD: 'Madrid, Spain',
    AMS: 'Amsterdam, Netherlands', DPS: 'Bali, Indonesia', MLE: 'Maldives', DXB: 'Dubai, UAE',
    KEF: 'Reykjavik, Iceland', ZAG: 'Zagreb, Croatia', DBV: 'Dubrovnik, Croatia',
    PRG: 'Prague, Czechia', CUN: 'Cancun, Mexico', BKK: 'Bangkok, Thailand', HKT: 'Phuket, Thailand',
    LCA: 'Larnaca, Cyprus', PFO: 'Paphos, Cyprus', VIE: 'Vienna, Austria', BUD: 'Budapest, Hungary',
    TLV: 'Tel Aviv, Israel', ETM: 'Eilat, Israel',
  }
  return cities[match.codes[0]] ?? value.trim()
}

function editDistance(a: string, b: string): number {
  const rows = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0))
  for (let i = 0; i <= a.length; i++) rows[i][0] = i
  for (let j = 0; j <= b.length; j++) rows[0][j] = j
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
    rows[i][j] = Math.min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
    if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) rows[i][j] = Math.min(rows[i][j], rows[i - 2][j - 2] + 1)
  }
  return rows[a.length][b.length]
}

// Fuzzy matches are suggestions requiring selection, never silent replacements.
export function destinationSuggestions(value: string): string[] {
  const input = normalizeDestination(value).slice(0, 200)
  if (input.length < 3 || destinationMatch(value)) return []
  return destinations.filter(d => d.automatic).map(d => {
    const aliases = d.names.flatMap(name => [name, ...(d.countries ?? []).flatMap(country => [`${name} ${country}`, `${country} ${name}`])])
    const distance = Math.min(...aliases.map(name => editDistance(input, name)))
    return { label: d.countries?.length ? `${d.names[0]}, ${d.countries[0]}` : d.names[0], distance }
  }).filter(item => item.distance <= (input.length >= 8 ? 2 : 1)).sort((a, b) => a.distance - b.distance).slice(0, 3).map(item => item.label)
}
