import { NextRequest } from 'next/server'
export const dynamic = 'force-dynamic'
export async function POST(request: NextRequest) {
  const base = (process.env.TRAVEL_AGENT_API_URL ?? '').replace(/\/$/, '')
  const token = process.env.TRAVEL_AGENT_WEB_TOKEN
  if (!base || !token) return Response.json({ error: 'שירות זיהוי היעדים אינו זמין כרגע' }, { status: 503 })
  try {
    const { query } = await request.json()
    if (typeof query !== 'string' || query.trim().length < 2 || query.length > 200) return Response.json({ error: 'הזינו שם עיר ומדינה' }, { status: 400 })
    const response = await fetch(`${base}/v1/web/destinations`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ query }), cache: 'no-store', signal: AbortSignal.timeout(15_000) })
    if (!response.ok) return Response.json({ error: 'לא הצלחנו לזהות את היעד. נסו שם עיר באנגלית ומדינה.' }, { status: 502 })
    return Response.json(await response.json())
  } catch { return Response.json({ error: 'זיהוי היעד אינו זמין כרגע. נסו שוב.' }, { status: 502 }) }
}
