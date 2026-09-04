export const dynamic = 'force-dynamic'

import { NextRequest } from 'next/server'
import { prisma } from '@/lib/prisma'
import {
  searchFlights,
  searchHotels,
  buildFlightsMarkdown,
  buildHotelsMarkdown,
} from '@/lib/serpapi'

const LLM_URL = 'https://apps.abacus.ai/v1/chat/completions'

// Use the LLM to map free-text destination -> destination IATA airport code + English hotel query.
async function extractSearchParams(destination: string): Promise<{
  arrivalId: string
  hotelQuery: string
}> {
  try {
    const res = await fetch(LLM_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${process.env.ABACUSAI_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'gemini-3.5-flash',
        messages: [
          {
            role: 'user',
            content: `A traveler wants to fly from Israel to this destination (text may be in Hebrew): "${destination}".
Return ONLY a compact JSON object, no markdown, with exactly these keys:
{"arrival_id":"<the 3-letter IATA airport code of the main international airport of that destination>","hotel_query":"<the destination city and country in English, suitable for a hotel search>"}
Example for "רומא איטליה": {"arrival_id":"FCO","hotel_query":"Rome, Italy"}`,
          },
        ],
        max_tokens: 150,
        response_format: { type: 'json_object' },
      }),
    })
    if (!res.ok) return { arrivalId: '', hotelQuery: destination }
    const data: any = await res.json()
    const content: string = data?.choices?.[0]?.message?.content ?? ''
    const cleaned = content.replace(/```json/gi, '').replace(/```/g, '').trim()
    const parsed = JSON.parse(cleaned)
    return {
      arrivalId: String(parsed?.arrival_id ?? '').toUpperCase().slice(0, 3),
      hotelQuery: String(parsed?.hotel_query ?? destination),
    }
  } catch (e) {
    console.error('extractSearchParams error:', e)
    return { arrivalId: '', hotelQuery: destination }
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const {
      name = '',
      email = '',
      phone = '',
      destination = '',
      dateFrom = '',
      dateTo = '',
      adults = 1,
      children = 0,
      budget = '',
      flightStops = 'any',
      travelStyles = [],
      specialRequests = '',
    } = body ?? {}

    // Validate required fields
    if (!name || !email || !destination) {
      return new Response(JSON.stringify({ error: 'שדות חובה חסרים' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // Save to DB first
    const inquiry = await prisma.tripInquiry.create({
      data: {
        name,
        email,
        phone,
        destination,
        dates: `${dateFrom} - ${dateTo}`,
        budgetLevel: budget,
        adults: Number(adults) || 1,
        children: Number(children) || 0,
        travelStyles: travelStyles ?? [],
        specialRequests: specialRequests || null,
        status: 'pending',
      },
    })

    const travelers = (Number(adults) || 0) + (Number(children) || 0)
    const stylesText = (travelStyles ?? []).join(', ') || 'ללא העדפה מיוחדת'

    const systemPrompt = `אתה סוכן נסיעות מקצועי, חם ומנוסה. אתה כותב תוכניות טיול מפורטות, מעשיות ומותאמות אישית בעברית בלבד.
התוכנית שלך צריכה להיות ברורה, מאורגנת ומעוררת השראה, עם דגש על חוויה מותאמת לתקציב ולסגנון הנוסעים.
כתוב את התשובה בפורמט Markdown נקי עם כותרות, רשימות ואימוג'ים מתאימים.`

    const userPrompt = `הכן תוכנית טיול מפורטת עבור הלקוח הבא:

- שם: ${name}
- יעד: ${destination}
- תאריכים: ${dateFrom} עד ${dateTo}
- מספר נוסעים: ${travelers} (${Number(adults) || 0} מבוגרים, ${Number(children) || 0} ילדים)
- רמת תקציב: ${budget || 'לא צוין'}
- סגנון נסיעה מועדף: ${stylesText}
- בקשות מיוחדות: ${specialRequests || 'אין'}

הערה חשובה: מערכת האתר מבצעת חיפוש חי של טיסות ומלונות אמיתיים עם מחירים וקישורי הזמנה, והם יוצגו בסוף התוכנית בסעיפים נפרדים. לכן אל תמציא מחירי טיסות או מלונות ספציפיים — במקום זאת הפנה את הלקוח לסעיפי הטיסות והמלונות הזמינים שבהמשך הדף.

התוכנית צריכה לכלול:
1. פתיח אישי וחם הפונה ללקוח בשמו.
2. סקירה קצרה על היעד ומה מייחד אותו.
3. ✈️ טיפים לטיסה: המלצות כלליות לגבי הטיסה (מתי כדאי להזמין, כבודה, שעות המראה/נחיתה מומלצות, טיפים לנמל התעופה). אל תציין מחירים — המחירים האמיתיים מופיעים בסעיף הטיסות הזמינות.
4. מסלול יומי מפורט (יום אחר יום) עם המלצות לאטרקציות, פעילויות וזמנים.
5. המלצות על אזורי לינה מתאימים לרמת התקציב (אל תציין מלונות ספציפיים עם מחירים — אלה מופיעים בסעיף המלונות הזמינים).
6. המלצות קולינריות (מסעדות/מאכלים מקומיים).
7. טיפים מעשיים (תחבורה, מזג אוויר, מה כדאי לארוז, אזהרות).
8. סיום מזמין עם הצעה ליצירת קשר להמשך התהליך.

חשוב מאוד: בכל פעם שא֪ה מזכיר מקום פיזי אמיתי שניתן למצוא במפה (אטרקציה, אתר, שכונה, מסעדה), עטוף את שם המקום בסוגריים מרובעים כפולים בדיוק כך: [[שם המקום]]. לדוגמה: [[הקולוסיאון]], [[מזרקת טרווי]]. אל תעטוף מילים שאינן מקומות פיזיים, ובפרט אל תעטוף שמות של חברות תעופה, חברות או מותגים. אלה יומרו לקישורים לגוגל מפות.

התאם את התוכנית למספר הימים שבין התאריכים. כתוב הכל בעברית.`

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      async start(controller) {
        let fullText = ''
        try {
          // Kick off live flight + hotel search in parallel with AI generation.
          const searchPromise = (async () => {
            const { arrivalId, hotelQuery } = await extractSearchParams(destination)
            const [flights, hotels] = await Promise.all([
              arrivalId
                ? searchFlights({
                    departureId: 'TLV',
                    arrivalId,
                    outboundDate: dateFrom,
                    returnDate: dateTo,
                    adults: Number(adults) || 1,
                    children: Number(children) || 0,
                    flightStops,
                  })
                : Promise.resolve([]),
              searchHotels({
                query: hotelQuery,
                checkIn: dateFrom,
                checkOut: dateTo,
                adults: Number(adults) || 1,
                children: Number(children) || 0,
              }),
            ])
            const flightsMd = buildFlightsMarkdown(flights, 'TLV', arrivalId, dateFrom, dateTo, flightStops)
            const hotelsMd = buildHotelsMarkdown(hotels, destination)
            return [flightsMd, hotelsMd].filter(Boolean).join('\n\n')
          })().catch((e) => {
            console.error('live search error:', e)
            return ''
          })

          const response = await fetch(LLM_URL, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${process.env.ABACUSAI_API_KEY}`,
            },
            body: JSON.stringify({
              model: 'gemini-3.5-flash',
              messages: [
                { role: 'system', content: systemPrompt },
                { role: 'user', content: userPrompt },
              ],
              stream: true,
              max_tokens: 3500,
            }),
          })

          if (!response?.ok) {
            const errText = await response?.text().catch(() => '')
            console.error('LLM API error:', response?.status, errText)
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({ status: 'error', message: 'שגיאה ביצירת תוכנית הטיול. נסו שוב.' })}\n\n`
              )
            )
            controller.close()
            return
          }

          const reader = response.body?.getReader()
          const decoder = new TextDecoder()
          let partialRead = ''

          while (reader) {
            const { done, value } = await reader.read()
            if (done) break
            partialRead += decoder.decode(value, { stream: true })
            const lines = partialRead.split('\n')
            partialRead = lines?.pop() ?? ''
            for (const line of lines ?? []) {
              const trimmed = line?.trim()
              if (!trimmed?.startsWith('data: ')) continue
              const data = trimmed.slice(6)
              if (data === '[DONE]') continue
              try {
                const parsed = JSON.parse(data)
                const delta = parsed?.choices?.[0]?.delta?.content || ''
                if (delta) {
                  fullText += delta
                  controller.enqueue(
                    encoder.encode(
                      `data: ${JSON.stringify({ status: 'processing' })}\n\n`
                    )
                  )
                }
              } catch {
                // skip invalid JSON chunks
              }
            }
          }

          if (!fullText.trim()) {
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({ status: 'error', message: 'לא התקבלה תשובה מהסוכן. נסו שוב.' })}\n\n`
              )
            )
            controller.close()
            return
          }

          // Append live flight + hotel search results to the AI plan.
          const liveData = await searchPromise
          if (liveData) {
            fullText += `\n\n---\n\n${liveData}`
          }

          // Update DB with AI response
          await prisma.tripInquiry
            .update({
              where: { id: inquiry?.id },
              data: { aiResponse: fullText, status: 'completed' },
            })
            .catch((e: any) => console.error('DB update error:', e))

          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ status: 'completed', result: fullText })}\n\n`
            )
          )
          controller.enqueue(encoder.encode('data: [DONE]\n\n'))
        } catch (err: any) {
          console.error('Generation error:', err)
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ status: 'error', message: 'שגיאה בהתחברות לסוכן. נסו שוב.' })}\n\n`
            )
          )
        } finally {
          controller.close()
        }
      },
    })

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
  } catch (err: any) {
    console.error('Submit route error:', err)
    return new Response(JSON.stringify({ error: err?.message ?? 'שגיאה פנימית' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
