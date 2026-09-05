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
] as const

export function airportCode(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim().toUpperCase()
  if (/^[A-Z]{3}$/.test(normalized)) return normalized
  const airport = airports.find(([code, label]) => `${label} (${code})`.toUpperCase() === normalized)
  return airport?.[0] ?? null
}
