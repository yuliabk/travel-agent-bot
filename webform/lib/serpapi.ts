// Live flight & hotel search via SerpAPI (Google Flights + Google Hotels engines).

export interface FlightLeg {
  airline: string
  from: string
  to: string
  duration: number
}

export interface FlightOption {
  airlines: string[]
  price: number | null
  totalDuration: number | null
  stops: number
  legs: FlightLeg[]
}

export interface HotelOption {
  name: string
  pricePerNight: string | null
  rating: number | null
  hotelClass: string | null
  link: string | null
}

const BASE = 'https://serpapi.com/search.json'

function fmtMinutes(min: number | null): string {
  if (!min || min <= 0) return ''
  const h = Math.floor(min / 60)
  const m = min % 60
  if (h && m) return `${h} שעות ו-${m} דקות`
  if (h) return `${h} שעות`
  return `${m} דקות`
}

export async function searchFlights(params: {
  departureId: string
  arrivalId: string
  outboundDate: string
  returnDate: string
  adults: number
  children: number
  flightStops?: 'any' | 'oneStop' | 'nonstop'
}): Promise<FlightOption[]> {
  const key = process.env.SERPAPI_API_KEY
  if (!key) return []
  const qs = new URLSearchParams({
    engine: 'google_flights',
    departure_id: params.departureId,
    arrival_id: params.arrivalId,
    outbound_date: params.outboundDate,
    return_date: params.returnDate,
    adults: String(Math.max(1, params.adults)),
    children: String(Math.max(0, params.children)),
    // SerpAPI stops: 0 = any, 1 = nonstop only, 2 = 1 stop or fewer
    stops:
      params.flightStops === 'nonstop'
        ? '1'
        : params.flightStops === 'oneStop'
        ? '2'
        : '0',
    currency: 'ILS',
    hl: 'iw',
    gl: 'il',
    api_key: key,
  })
  try {
    const res = await fetch(`${BASE}?${qs.toString()}`, { cache: 'no-store' })
    if (!res.ok) return []
    const data: any = await res.json()
    const list: any[] = [...(data?.best_flights ?? []), ...(data?.other_flights ?? [])]
    return list.slice(0, 4).map((f: any): FlightOption => {
      const legs: FlightLeg[] = (f?.flights ?? []).map((l: any) => ({
        airline: l?.airline ?? '',
        from: l?.departure_airport?.id ?? '',
        to: l?.arrival_airport?.id ?? '',
        duration: Number(l?.duration) || 0,
      }))
      const airlines = Array.from(new Set(legs.map((l) => l.airline).filter(Boolean)))
      return {
        airlines,
        price: typeof f?.price === 'number' ? f.price : null,
        totalDuration: typeof f?.total_duration === 'number' ? f.total_duration : null,
        stops: Math.max(0, legs.length - 1),
        legs,
      }
    })
  } catch (e) {
    console.error('searchFlights error:', e)
    return []
  }
}

export async function searchHotels(params: {
  query: string
  checkIn: string
  checkOut: string
  adults: number
  children: number
}): Promise<HotelOption[]> {
  const key = process.env.SERPAPI_API_KEY
  if (!key) return []
  const qs = new URLSearchParams({
    engine: 'google_hotels',
    q: params.query,
    check_in_date: params.checkIn,
    check_out_date: params.checkOut,
    adults: String(Math.max(1, params.adults)),
    children: String(Math.max(0, params.children)),
    currency: 'ILS',
    hl: 'iw',
    gl: 'il',
    api_key: key,
  })
  try {
    const res = await fetch(`${BASE}?${qs.toString()}`, { cache: 'no-store' })
    if (!res.ok) return []
    const data: any = await res.json()
    const props: any[] = data?.properties ?? []
    return props.slice(0, 5).map((p: any): HotelOption => ({
      name: p?.name ?? '',
      pricePerNight: p?.rate_per_night?.lowest ?? null,
      rating: typeof p?.overall_rating === 'number' ? p.overall_rating : null,
      hotelClass: p?.hotel_class ?? null,
      link: p?.link ?? null,
    }))
  } catch (e) {
    console.error('searchHotels error:', e)
    return []
  }
}

export function buildFlightsMarkdown(
  flights: FlightOption[],
  departureId: string,
  arrivalId: string,
  outboundDate: string,
  returnDate: string,
  flightStops: 'any' | 'oneStop' | 'nonstop' = 'any'
): string {
  const searchUrl = `https://www.google.com/travel/flights?q=${encodeURIComponent(
    `flights from ${departureId} to ${arrivalId} on ${outboundDate} through ${returnDate}`
  )}`
  if (!flights.length) {
    if (flightStops === 'nonstop') {
      return [
        '## ✈️ טיסות זמינות עכשיו (חיפוש חי)',
        `לא נמצאו טיסות ישירות (ללא עצירות) מ-${departureId} ל-${arrivalId} בתאריכים שביקשתם. ניתן לנסות תאריכים אחרים או לשנות את סינון הטיסות כדי לראות טיסות עם עצירת ביניים.`,
        `[🔎 לצפייה בכל הטיסות והזמנה בגוגל טיסות](${searchUrl})`,
      ].join('\n')
    }
    if (flightStops === 'oneStop') {
      return [
        '## ✈️ טיסות זמינות עכשיו (חיפוש חי)',
        `לא נמצאו טיסות עם עד עצירה אחת מ-${departureId} ל-${arrivalId} בתאריכים שביקשתם. ניתן לנסות תאריכים אחרים או לשנות את סינון הטיסות כדי לראות את כל הטיסות.`,
        `[🔎 לצפייה בכל הטיסות והזמנה בגוגל טיסות](${searchUrl})`,
      ].join('\n')
    }
    return ''
  }
  const title =
    flightStops === 'nonstop'
      ? '## ✈️ טיסות ישירות זמינות עכשיו (חיפוש חי)'
      : flightStops === 'oneStop'
      ? '## ✈️ טיסות (עד עצירה אחת) זמינות עכשיו (חיפוש חי)'
      : '## ✈️ טיסות זמינות עכשיו (חיפוש חי)'
  const lines: string[] = [title]
  lines.push(`להלן טיסות אמיתיות שנמצאו כעת מ-${departureId} ל-${arrivalId} בתאריכים שביקשתם:`)
  flights.forEach((f) => {
    const airline = f.airlines.join(' + ') || 'חברת תעופה'
    const stopsTxt = f.stops === 0 ? 'טיסה ישירה' : `${f.stops} עצירת ביניים`
    const dur = fmtMinutes(f.totalDuration)
    const price = f.price != null ? `כ-₪${f.price.toLocaleString('en-US')} לנוסע (הלוך-חזור)` : 'מחיר בבדיקה'
    const durTxt = dur ? ` · משך: ${dur}` : ''
    lines.push(`- **${airline}** — ${stopsTxt}${durTxt} · ${price}`)
  })
  lines.push(`[🔎 לצפייה בכל הטיסות והזמנה בגוגל טיסות](${searchUrl})`)
  return lines.join('\n')
}

export function buildHotelsMarkdown(hotels: HotelOption[], destination: string): string {
  if (!hotels.length) return ''
  const lines: string[] = ['## 🏨 מלונות זמינים עכשיו (חיפוש חי)']
  lines.push(`להלן מלונות אמיתיים ב-${destination} עם מחירים זמינים כעת:`)
  hotels.forEach((h) => {
    const rating = h.rating != null ? ` · ⭐ ${h.rating}` : ''
    const cls = h.hotelClass ? ` · ${h.hotelClass}` : ''
    const price = h.pricePerNight ? ` · ${h.pricePerNight} ללילה` : ''
    const name = h.link ? `[${h.name}](${h.link})` : `**${h.name}**`
    lines.push(`- ${name}${price}${rating}${cls}`)
  })
  return lines.join('\n')
}

export interface GeoPoint {
  name: string
  lat: number
  lng: number
}

// Geocode a single place name to GPS coordinates using SerpAPI Google Maps engine.
export async function geocodePlace(query: string): Promise<{ lat: number; lng: number } | null> {
  const key = process.env.SERPAPI_API_KEY
  if (!key) return null
  const qs = new URLSearchParams({
    engine: 'google_maps',
    q: query,
    hl: 'iw',
    gl: 'il',
    api_key: key,
  })
  try {
    const res = await fetch(`${BASE}?${qs.toString()}`, { cache: 'no-store' })
    if (!res.ok) return null
    const data: any = await res.json()
    let gps = data?.place_results?.gps_coordinates
    if (!gps) {
      const first = (data?.local_results ?? [])[0]
      gps = first?.gps_coordinates
    }
    if (gps && typeof gps.latitude === 'number' && typeof gps.longitude === 'number') {
      return { lat: gps.latitude, lng: gps.longitude }
    }
    return null
  } catch (e) {
    console.error('geocodePlace error:', e)
    return null
  }
}

// Geocode many places with limited concurrency; keeps only those that resolve.
export async function geocodePlaces(places: string[], destination: string): Promise<GeoPoint[]> {
  const unique = Array.from(new Set(places.map((p) => p.trim()).filter(Boolean))).slice(0, 40)
  const slots: (GeoPoint | null)[] = new Array(unique.length).fill(null)
  const concurrency = 4
  let idx = 0
  async function worker() {
    while (idx < unique.length) {
      const cur = idx++
      const name = unique[cur]
      const query = destination && !name.includes(destination) ? `${name}, ${destination}` : name
      const gps = await geocodePlace(query)
      if (gps) slots[cur] = { name, lat: gps.lat, lng: gps.lng }
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, unique.length) }, () => worker()))
  return slots.filter((s): s is GeoPoint => s !== null)
}

// Escape a string for safe inclusion inside XML/KML text nodes.
function kmlEsc(s: string): string {
  return (s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// Build a KML document (Google Earth / Google My Maps format) from geocoded points.
export function buildKml(points: GeoPoint[], mapName: string): string {
  const placemarks = points
    .map(
      (p, i) => `    <Placemark>
      <name>${kmlEsc(`${i + 1}. ${p.name}`)}</name>
      <description>${kmlEsc(p.name)}</description>
      <Point><coordinates>${p.lng},${p.lat},0</coordinates></Point>
    </Placemark>`
    )
    .join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${kmlEsc(mapName)}</name>
${placemarks}
  </Document>
</kml>`
}

export interface DayPoints {
  label: string
  points: GeoPoint[]
}

// Distinct pre-colored Google Maps marker icons cycled per day.
// Google My Maps honors these icon URLs on import (unlike a <color>-tinted
// generic pushpin, which My Maps resets to a default "uniform" color).
const DAY_ICONS = [
  { icon: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png', label: 'ffe8112d' },
  { icon: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png', label: 'ffe8731e' },
  { icon: 'https://maps.google.com/mapfiles/ms/icons/green-dot.png', label: 'ff2e9e1f' },
  { icon: 'https://maps.google.com/mapfiles/ms/icons/orange-dot.png', label: 'ff2e77e8' },
  { icon: 'https://maps.google.com/mapfiles/ms/icons/purple-dot.png', label: 'ffaa248e' },
  { icon: 'https://maps.google.com/mapfiles/ms/icons/ltblue-dot.png', label: 'ff8f9e1f' },
  { icon: 'https://maps.google.com/mapfiles/ms/icons/pink-dot.png', label: 'ff6331e9' },
  { icon: 'https://maps.google.com/mapfiles/ms/icons/yellow-dot.png', label: 'ff25a8f9' },
]

// Build a KML document with one colored Folder (layer) per day.
// Each day uses a distinct pre-colored marker icon + a StyleMap (normal +
// highlight), the format Google My Maps reads to keep per-layer colors.
export function buildKmlByDays(days: DayPoints[], mapName: string): string {
  const styles = days
    .map((_, i) => {
      const { icon, label } = DAY_ICONS[i % DAY_ICONS.length]
      const iconStyle = `      <IconStyle>
        <scale>1.1</scale>
        <Icon><href>${icon}</href></Icon>
        <hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/>
      </IconStyle>
      <LabelStyle><color>${label}</color></LabelStyle>`
      return `    <Style id="day${i}-normal">
${iconStyle}
    </Style>
    <Style id="day${i}-highlight">
${iconStyle}
    </Style>
    <StyleMap id="day${i}">
      <Pair><key>normal</key><styleUrl>#day${i}-normal</styleUrl></Pair>
      <Pair><key>highlight</key><styleUrl>#day${i}-highlight</styleUrl></Pair>
    </StyleMap>`
    })
    .join('\n')

  const folders = days
    .map((d, di) => {
      const placemarks = d.points
        .map(
          (p, i) => `        <Placemark>
          <name>${kmlEsc(`${i + 1}. ${p.name}`)}</name>
          <description>${kmlEsc(`${d.label} — ${p.name}`)}</description>
          <styleUrl>#day${di}</styleUrl>
          <Point><coordinates>${p.lng},${p.lat},0</coordinates></Point>
        </Placemark>`
        )
        .join('\n')
      return `    <Folder>
      <name>${kmlEsc(d.label)}</name>
${placemarks}
    </Folder>`
    })
    .join('\n')

  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${kmlEsc(mapName)}</name>
${styles}
${folders}
  </Document>
</kml>`
}
