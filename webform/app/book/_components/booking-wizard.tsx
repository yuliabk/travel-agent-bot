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

export interface FormData {
  name: string
  email: string
  phone: string
  destination: string
  dateFrom: string
  dateTo: string
  adults: number
  children: number
  budget: string
  flightStops: 'any' | 'oneStop' | 'nonstop'
  travelStyles: string[]
  specialRequests: string
}

const defaultForm: FormData = {
  name: '',
  email: '',
  phone: '',
  destination: '',
  dateFrom: '',
  dateTo: '',
  adults: 2,
  children: 0,
  budget: '',
  flightStops: 'any',
  travelStyles: [],
  specialRequests: '',
}

const stepLabels = ['פרטים אישיים', 'פרטי הטיול', 'העדפות', 'סיכום']

export function BookingWizard() {
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<FormData>(defaultForm)
  const [loading, setLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const updateForm = (partial: Partial<FormData>) => {
    setForm((prev: FormData) => ({ ...(prev ?? {}), ...partial }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })

      if (!res?.ok) {
        throw new Error('שגיאה בשליחת הבקשה')
      }

      const reader = res?.body?.getReader()
      if (!reader) throw new Error('לא ניתן לקרוא את התשובה')

      const decoder = new TextDecoder()
      let buffer = ''
      let partialRead = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        partialRead += decoder.decode(value, { stream: true })
        const lines = partialRead.split('\n')
        partialRead = lines?.pop() ?? ''
        for (const line of lines ?? []) {
          if (line?.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue
            try {
              const parsed = JSON.parse(data)
              if (parsed?.status === 'completed') {
                setAiResponse(parsed?.result ?? '')
                setLoading(false)
                return
              } else if (parsed?.status === 'error') {
                throw new Error(parsed?.message ?? 'שגיאה')
              }
            } catch (e: any) {
              // skip invalid JSON chunks
            }
          }
        }
      }
      // If we got here without completed status, check buffer
      if (!aiResponse) {
        setError('לא התקבלה תשובה מהשרת')
      }
    } catch (err: any) {
      console.error('Submit error:', err)
      setError(err?.message ?? 'שגיאה לא צפויה')
    } finally {
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
              <StepSummary form={form} onBack={() => setStep(2)} onSubmit={handleSubmit} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
