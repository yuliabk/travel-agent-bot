'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { StepPersonal } from './step-personal'
import { StepTrip } from './step-trip'
import { StepPreferences } from './step-preferences'
import { StepSummary } from './step-summary'
import { ResultCard } from './result-card'
import { LoadingAnimation } from './loading-animation'
import { Check } from 'lucide-react'
import { destinationAirportCode } from '@/lib/airports'

export interface FormData {
  name: string
  email: string
  phone: string
  origin: string
  destination: string
  originAirport: string
  destinationAirport: string
  landingAirportManual?: boolean
  alternativeAirports?: string
  stays?: { destination: string; checkIn: string; checkOut: string }[]
  dateFrom: string
  dateTo: string
  adults: number
  children: number
  childAges: number[]
  budgetAmount: string
  currency: 'ILS' | 'USD' | 'EUR' | 'GBP'
  flightStops: 'any' | 'oneStop' | 'nonstop'
  travelStyles: string[]
  specialRequests: string
  consent: boolean
}

const defaultForm: FormData = {
  name: '',
  email: '',
  phone: '',
  origin: '',
  destination: '',
  originAirport: '',
  destinationAirport: '',
  landingAirportManual: false,
  alternativeAirports: '',
  stays: [],
  dateFrom: '',
  dateTo: '',
  adults: 2,
  children: 0,
  childAges: [],
  budgetAmount: '',
  currency: 'ILS',
  flightStops: 'any',
  travelStyles: [],
  specialRequests: '',
  consent: false,
}

const stepLabels = ['פרטים אישיים', 'פרטי הטיול', 'העדפות', 'סיכום']

export function BookingWizard() {
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<FormData>(defaultForm)
  const [loading, setLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const updateForm = (partial: Partial<FormData>) => {
    setForm((prev: FormData) => ({ ...prev, ...partial,
      ...(partial.destination !== undefined && partial.destination !== prev.destination && !prev.landingAirportManual && partial.destinationAirport === undefined
        ? { destinationAirport: destinationAirportCode(partial.destination) ?? '' } : {}),
    }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)

    // Abort the request if it stalls, so the user never gets stuck on an
    // endless loading spinner ("nothing happens"). The timer is reset on every
    // chunk we receive, so a slow-but-alive stream is never cut off.
    const STALL_MS = 90000
    const controller = new AbortController()
    let stallTimer: ReturnType<typeof setTimeout> | null = null
    let stalled = false
    const armStall = () => {
      if (stallTimer) clearTimeout(stallTimer)
      stallTimer = setTimeout(() => {
        stalled = true
        controller.abort()
      }, STALL_MS)
    }
    const clearStall = () => {
      if (stallTimer) clearTimeout(stallTimer)
      stallTimer = null
    }

    try {
      armStall()
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
        signal: controller.signal,
      })

      if (!res?.ok) {
        let serverMsg = ''
        try {
          const errJson = await res.json()
          serverMsg = errJson?.error ?? ''
        } catch {
          // ignore non-JSON error bodies
        }
        throw new Error(serverMsg || 'שגיאה בשליחת הבקשה. נסו שוב.')
      }

      const reader = res?.body?.getReader()
      if (!reader) throw new Error('לא ניתן לקרוא את התשובה מהשרת')

      const decoder = new TextDecoder()
      let partialRead = ''
      let gotAnyData = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        armStall() // we're alive — reset the stall timer
        gotAnyData = true
        partialRead += decoder.decode(value, { stream: true })
        const lines = partialRead.split('\n')
        partialRead = lines?.pop() ?? ''
        for (const line of lines ?? []) {
          if (!line?.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') continue
          let parsed: any = null
          try {
            parsed = JSON.parse(data)
          } catch {
            continue // skip invalid JSON chunks
          }
          if (parsed?.status === 'completed') {
            clearStall()
            setAiResponse(parsed?.result ?? '')
            setLoading(false)
            return
          }
          if (parsed?.status === 'error') {
            throw new Error(parsed?.message ?? 'שגיאה ביצירת התוכנית. נסו שוב.')
          }
        }
      }
      // Stream ended without a 'completed' event.
      throw new Error(
        gotAnyData
          ? 'החיבור לסוכן נקטע לפני שהתוכנית הושלמה. נסו שוב.'
          : 'לא התקבלה תשובה מהסוכן. נסו שוב.'
      )
    } catch (err: any) {
      console.error('Submit error:', err)
      if (stalled || err?.name === 'AbortError') {
        setError('הבקשה ארכה זמן רב מדי והופסקה. ייתכן שיש עומס או בעיית חיבור זמנית — אנא נסו שוב.')
      } else {
        setError(err?.message ?? 'אירעה שגיאה לא צפויה. נסו שוב.')
      }
    } finally {
      clearStall()
      setLoading(false)
    }
  }

  if (loading) return <LoadingAnimation />
  if (aiResponse) return <ResultCard response={aiResponse} form={form} />

  return (
    <div>
      {/* Step indicator */}
      <div className="flex items-center justify-center gap-2 mb-8">
        {stepLabels?.map((label: string, i: number) => (
          <div key={i} className="flex items-center gap-2">
            <div className="flex flex-col items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                  i < step
                    ? 'bg-primary text-primary-foreground'
                    : i === step
                    ? 'bg-primary text-primary-foreground shadow-lg'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {i < step ? <Check className="h-5 w-5" /> : i + 1}
              </div>
              <span className={`text-xs mt-1 hidden sm:block ${i <= step ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                {label}
              </span>
            </div>
            {i < (stepLabels?.length ?? 0) - 1 && (
              <div className={`w-8 sm:w-16 h-0.5 mb-5 sm:mb-4 ${i < step ? 'bg-primary' : 'bg-muted'}`} />
            )}
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">
          {error}
        </div>
      )}

      <div className="bg-card rounded-xl shadow-[var(--shadow-md)] p-6 sm:p-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.3 }}
          >
            {step === 0 && (
              <StepPersonal form={form} updateForm={updateForm} onNext={() => setStep(1)} />
            )}
            {step === 1 && (
              <StepTrip form={form} updateForm={updateForm} onNext={() => setStep(2)} onBack={() => setStep(0)} />
            )}
            {step === 2 && (
              <StepPreferences form={form} updateForm={updateForm} onNext={() => setStep(3)} onBack={() => setStep(1)} />
            )}
            {step === 3 && (
              <StepSummary form={form} updateForm={updateForm} onBack={() => setStep(2)} onSubmit={handleSubmit} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
