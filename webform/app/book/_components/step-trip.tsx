'use client'

import { FormData } from './booking-wizard'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { MapPin, Calendar, Users, Wallet, ArrowLeft, ArrowRight, Minus, Plus, Plane } from 'lucide-react'
import { useState } from 'react'

interface Props {
  form: FormData
  updateForm: (partial: Partial<FormData>) => void
  onNext: () => void
  onBack: () => void
}

const popularDestinations = [
  'יוון', 'פריז', 'רומא', 'ברצלונה', 'לונדון', 'ניו יורק',
  'אמסטרדם', 'סנטוריני', 'באלי', 'מלדיבים', 'טוקיו',
  'דובאי', 'איסלנד', 'קרואטיה', 'פראג', 'קנקון',
]

const budgetOptions = [
  { value: 'כלכלי', label: 'כלכלי 💰' },
  { value: 'בינוני', label: 'בינוני 💰💰' },
  { value: 'פרמיום', label: 'פרמיום 💰💰💰' },
  { value: 'ללא הגבלה', label: 'ללא הגבלה ✨' },
]

const flightStopsOptions: { value: 'any' | 'oneStop' | 'nonstop'; label: string }[] = [
  { value: 'any', label: 'כל הטיסות' },
  { value: 'oneStop', label: 'עד עצירה אחת' },
  { value: 'nonstop', label: 'טיסות ישירות' },
]

export function StepTrip({ form, updateForm, onNext, onBack }: Props) {
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [showSuggestions, setShowSuggestions] = useState(false)

  const filteredDests = popularDestinations?.filter((d: string) =>
    d?.includes(form?.destination ?? '')
  ) ?? []

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!(form?.destination ?? '').trim()) errs.destination = 'נא הזינו יעד'
    if (!(form?.dateFrom ?? '')) errs.dateFrom = 'נא בחרו תאריך התחלה'
    if (!(form?.dateTo ?? '')) errs.dateTo = 'נא בחרו תאריך סיום'
    if (!(form?.budget ?? '')) errs.budget = 'נא בחרו תקציב'
    setErrors(errs)
    return Object.keys(errs ?? {})?.length === 0
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-2">
        <h2 className="font-display text-xl font-semibold">פרטי הטיול</h2>
        <p className="text-sm text-muted-foreground">לאן אתם רוצים לטוס?</p>
      </div>

      <div className="space-y-4">
        {/* Destination */}
        <div className="relative">
          <Label htmlFor="destination" className="mb-1.5 block">יעד הנסיעה</Label>
          <div className="relative">
            <MapPin className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              id="destination"
              placeholder="לדוגמה: יוון, פריז, רומא..."
              value={form?.destination ?? ''}
              onChange={(e: any) => {
                updateForm({ destination: e?.target?.value ?? '' })
                setShowSuggestions(true)
              }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              className="pr-10"
              variant={errors?.destination ? 'error' : 'default'}
            />
          </div>
          {showSuggestions && (form?.destination ?? '').length > 0 && (filteredDests?.length ?? 0) > 0 && (
            <div className="absolute z-20 top-full mt-1 w-full bg-popover rounded-lg shadow-lg border border-border max-h-48 overflow-auto">
              {filteredDests?.map((d: string) => (
                <button
                  key={d}
                  type="button"
                  className="w-full text-right px-4 py-2 text-sm hover:bg-muted transition-colors"
                  onMouseDown={() => {
                    updateForm({ destination: d })
                    setShowSuggestions(false)
                  }}
                >
                  {d}
                </button>
              ))}
            </div>
          )}
          {errors?.destination && <p className="text-destructive text-xs mt-1">{errors.destination}</p>}
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="dateFrom" className="mb-1.5 block">תאריך התחלה</Label>
            <div className="relative">
              <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="dateFrom"
                type="date"
                value={form?.dateFrom ?? ''}
                onChange={(e: any) => updateForm({ dateFrom: e?.target?.value ?? '' })}
                className="pr-10"
                variant={errors?.dateFrom ? 'error' : 'default'}
              />
            </div>
            {errors?.dateFrom && <p className="text-destructive text-xs mt-1">{errors.dateFrom}</p>}
          </div>
          <div>
            <Label htmlFor="dateTo" className="mb-1.5 block">תאריך סיום</Label>
            <div className="relative">
              <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="dateTo"
                type="date"
                value={form?.dateTo ?? ''}
                onChange={(e: any) => updateForm({ dateTo: e?.target?.value ?? '' })}
                className="pr-10"
                variant={errors?.dateTo ? 'error' : 'default'}
              />
            </div>
            {errors?.dateTo && <p className="text-destructive text-xs mt-1">{errors.dateTo}</p>}
          </div>
        </div>

        {/* Travelers */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label className="mb-1.5 block">מבוגרים</Label>
            <div className="flex items-center gap-3 bg-muted/50 rounded-lg p-3">
              <Users className="h-4 w-4 text-muted-foreground" />
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                onClick={() => updateForm({ adults: Math.max(1, (form?.adults ?? 1) - 1) })}
              >
                <Minus className="h-3 w-3" />
              </Button>
              <span className="font-semibold min-w-[2ch] text-center">{form?.adults ?? 1}</span>
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                onClick={() => updateForm({ adults: (form?.adults ?? 1) + 1 })}
              >
                <Plus className="h-3 w-3" />
              </Button>
            </div>
          </div>
          <div>
            <Label className="mb-1.5 block">ילדים</Label>
            <div className="flex items-center gap-3 bg-muted/50 rounded-lg p-3">
              <Users className="h-4 w-4 text-muted-foreground" />
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                onClick={() => updateForm({ children: Math.max(0, (form?.children ?? 0) - 1) })}
              >
                <Minus className="h-3 w-3" />
              </Button>
              <span className="font-semibold min-w-[2ch] text-center">{form?.children ?? 0}</span>
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                onClick={() => updateForm({ children: (form?.children ?? 0) + 1 })}
              >
                <Plus className="h-3 w-3" />
              </Button>
            </div>
          </div>
        </div>

        {/* Budget */}
        <div>
          <Label className="mb-1.5 block">תקציב משוער</Label>
          <Select value={form?.budget ?? ''} onValueChange={(v: string) => updateForm({ budget: v })}>
            <SelectTrigger className={errors?.budget ? 'border-destructive' : ''}>
              <div className="flex items-center gap-2">
                <Wallet className="h-4 w-4 text-muted-foreground" />
                <SelectValue placeholder="בחרו תקציב" />
              </div>
            </SelectTrigger>
            <SelectContent>
              {budgetOptions?.map((opt: any) => (
                <SelectItem key={opt?.value} value={opt?.value ?? ''}>{opt?.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors?.budget && <p className="text-destructive text-xs mt-1">{errors.budget}</p>}
        </div>

        {/* Flight stops preference */}
        <div>
          <Label className="mb-1.5 block">עצירות בטיסה</Label>
          <div className="grid grid-cols-3 gap-2">
            {flightStopsOptions.map((opt) => {
              const active = (form?.flightStops ?? 'any') === opt.value
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => updateForm({ flightStops: opt.value })}
                  className={`flex flex-col items-center gap-1 rounded-lg border p-3 text-center transition-colors ${
                    active
                      ? 'border-primary bg-primary/5'
                      : 'border-border bg-muted/50 hover:bg-muted'
                  }`}
                >
                  <Plane className={`h-4 w-4 ${active ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className={`text-xs font-medium ${active ? 'text-primary' : 'text-foreground'}`}>{opt.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          <ArrowRight className="ml-2 h-4 w-4" />
          חזרה
        </Button>
        <Button onClick={() => validate() && onNext()}>
          <ArrowLeft className="ml-2 h-4 w-4" />
          המשך
        </Button>
      </div>
    </div>
  )
}
