export const dynamic = 'force-dynamic'

import { NextRequest } from 'next/server'
import { airportCode, destinationAirportCode, canonicalDestination, destinationSuggestions } from '@/lib/airports'

const API_TIMEOUT_MS = 90_000

const missingFieldLabels: Record<string, string> = {
  origin: 'מוצא',
  budget: 'תקציב',
  currency: 'מטבע',
  consent_status: 'אישור פרטיות',
  child_ages: 'גילי הילדים',
  departure_date: 'תאריך יציאה',
  return_date: 'תאריך חזרה',
  origin_iata: 'שדה המראה',
  destination_iata: 'שדה נחיתה',
  stays: 'מקומות לינה ותאריכים רצופים לכל לילות הטיול',
}

function apiBase(): string {
  return (process.env.TRAVEL_AGENT_API_URL ?? '').replace(/\/$/, '')
}

export async function POST(request: NextRequest) {
  const base = apiBase()
  const token = process.env.TRAVEL_AGENT_WEB_TOKEN ?? ''
  if (!base || !token) {
    return Response.json(
      { error: 'שירות תכנון הטיולים עדיין אינו מופעל בסביבה זו.' },
      { status: 503 }
    )
  }

  try {
    const body = await request.json()
    const {
      name = '',
      email = '',
      phone = '',
      origin = '',
      destination = '',
      originAirport = '',
      destinationAirport = '',
      landingAirportManual = false,
      alternativeAirports = '',
      stays = [],
      dateFrom = '',
      dateTo = '',
      adults = 1,
      children = 0,
      childAges = [],
      budgetAmount = '',
      currency = 'ILS',
      flightStops = 'any',
      carRental = false,
      travelStyles = [],
      specialRequests = '',
      consent = false,
    } = body ?? {}

    if (!name || !email || !origin || !destination || !dateFrom || !dateTo) {
      return Response.json({ error: 'שדות חובה חסרים' }, { status: 400 })
    }
    if (!consent) {
      return Response.json({ error: 'יש לאשר את תנאי הפרטיות לפני יצירת הטיוטה.' }, { status: 400 })
    }
    const numericBudget = Number(budgetAmount)
    if (!Number.isFinite(numericBudget) || numericBudget <= 0) {
      return Response.json({ error: 'יש להזין תקציב מספרי תקין.' }, { status: 400 })
    }
    const normalizedAges = Array.isArray(childAges)
      ? childAges.map((v: unknown) => Number(v)).filter((v: number) => Number.isInteger(v) && v >= 0 && v <= 17)
      : []
    if (Number(children) > 0 && normalizedAges.length !== Number(children)) {
      return Response.json({ error: 'יש להזין גיל עבור כל ילד.' }, { status: 400 })
    }

    const originIata = airportCode(originAirport)
    if (typeof destination !== 'string' || destinationSuggestions(destination).length) return Response.json({ error: 'בחרו את השם המתוקן של יעד הנסיעה או ציינו עיר ומדינה.' }, { status: 422 })
    const destinationIata = destinationAirportCode(destination, destinationAirport, landingAirportManual === true)
    if (!originIata || !destinationIata || originIata === destinationIata) {
      return Response.json({ error: 'בחרו שדות המראה ונחיתה שונים ותקינים בפרטי הטיול.' }, { status: 422 })
    }

    if (!Array.isArray(stays) || stays.length > 6) return Response.json({ error: 'אפשר להזין עד שישה מקומות לינה.' }, { status: 422 })
    let cursor = dateFrom
    for (const stay of stays) {
      if (typeof stay?.destination !== 'string' || !stay.destination.trim() || destinationSuggestions(stay.destination).length || stay.checkIn !== cursor || !/^\d{4}-\d{2}-\d{2}$/.test(stay.checkOut) || stay.checkOut <= stay.checkIn || stay.checkOut > dateTo) return Response.json({ error: 'בדקו שמות מקומות לינה ותאריכים: נדרשים לילות רצופים ללא חפיפה או לילות חסרים.' }, { status: 422 })
      cursor = stay.checkOut
    }
    if (stays.length && cursor !== dateTo) return Response.json({ error: 'יש לכסות את כל לילות הטיול במקומות הלינה.' }, { status: 422 })
    const alternativeCodes = typeof alternativeAirports === 'string' ? alternativeAirports.split(/[,\s]+/).filter(Boolean).map(airportCode) : [null]
    if (alternativeCodes.length > 3 || alternativeCodes.some(code => !code)) return Response.json({ error: 'הזינו עד שלושה קודי שדות חלופיים בני שלוש אותיות.' }, { status: 422 })
    const backendPayload = {
      stays: stays.map(stay => ({ destination: canonicalDestination(stay.destination), check_in: stay.checkIn, check_out: stay.checkOut })),
      alternative_airports: alternativeCodes,
      origin_iata: originIata,
      destination_iata: destinationIata,
      payload: {
        name,
        email,
        phone: phone || null,
        destination: canonicalDestination(destination),
        dateFrom,
        dateTo,
        adults: Number(adults) || 1,
        children: Number(children) || 0,
        budget: `${numericBudget} ${currency}`,
        flightStops,
        carRental: carRental === true,
        travelStyles: Array.isArray(travelStyles) ? travelStyles : [],
        specialRequests: specialRequests || null,
      },
      completion: {
        origin,
        budget_amount: numericBudget,
        currency,
        consent_status: 'granted',
        child_ages: normalizedAges,
      },
    }

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS)
    let response: Response
    try {
      response = await fetch(`${base}/v1/web/draft`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(backendPayload),
        cache: 'no-store',
        signal: controller.signal,
      })
    } finally {
      clearTimeout(timer)
    }

    let data: any = null
    try {
      data = await response.json()
    } catch {
      data = null
    }

    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : ''
      const message = response.status === 503
        ? 'שירות הטיוטות עדיין לא הופעל. נסו שוב לאחר הפעלת סביבת ה-Web המאובטחת.'
        : detail || 'שגיאה ביצירת טיוטת הטיול. נסו שוב.'
      return Response.json({ error: message }, { status: response.status })
    }

    if (data?.status === 'NEEDS_INFORMATION') {
      const fields = Array.isArray(data?.missing_fields) ? data.missing_fields : []
      const readable = fields.map((f: string) => missingFieldLabels[f] ?? f).join(', ')
      return Response.json(
        { error: readable ? `חסרים פרטים: ${readable}` : 'חסרים פרטים להשלמת הבקשה.' },
        { status: 422 }
      )
    }

    const result = String(data?.rendered_draft ?? '').trim()
    if (!result) {
      return Response.json({ error: 'לא התקבלה טיוטה מהמערכת.' }, { status: 502 })
    }

    // Keep the existing SSE shape so the current UX does not need to change.
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ status: 'processing' })}\n\n`))
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({
              status: 'completed',
              result,
              proposalStatus: data?.status ?? 'PARTIAL_DRAFT',
              proposalId: data?.proposal?.proposal_id ?? null,
              proposalVersion: data?.proposal?.version ?? null,
            })}\n\n`
          )
        )
        controller.enqueue(encoder.encode('data: [DONE]\n\n'))
        controller.close()
      },
    })

    return new Response(stream, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        Connection: 'keep-alive',
      },
    })
  } catch (error: any) {
    console.error('submit proxy error:', error)
    const timedOut = error?.name === 'AbortError'
    return Response.json(
      { error: timedOut ? 'הבקשה ארכה זמן רב מדי. נסו שוב.' : 'אירעה שגיאה זמנית. נסו שוב.' },
      { status: timedOut ? 504 : 500 }
    )
  }
}
