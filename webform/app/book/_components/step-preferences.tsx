'use client'

import { FormData } from './booking-wizard'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ArrowLeft, ArrowRight, Waves, Building2, Trees, Landmark, Mountain, Sparkles } from 'lucide-react'

interface Props {
  form: FormData
  updateForm: (partial: Partial<FormData>) => void
  onNext: () => void
  onBack: () => void
}

const travelStyleOptions = [
  { value: 'חוף ים', label: 'חוף ים', icon: Waves },
  { value: 'ערים', label: 'ערים', icon: Building2 },
  { value: 'טבע', label: 'טבע', icon: Trees },
  { value: 'תרבות', label: 'תרבות', icon: Landmark },
  { value: 'הרפתקאות', label: 'הרפתקאות', icon: Mountain },
  { value: 'ספא', label: 'ספא ורוגע', icon: Sparkles },
]

export function StepPreferences({ form, updateForm, onNext, onBack }: Props) {
  const styles = form?.travelStyles ?? []

  const toggleStyle = (style: string) => {
    if (styles?.includes(style)) {
      updateForm({ travelStyles: styles?.filter((s: string) => s !== style) ?? [] })
    } else {
      updateForm({ travelStyles: [...(styles ?? []), style] })
    }
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-2">
        <h2 className="font-display text-xl font-semibold">העדפות ובקשות</h2>
        <p className="text-sm text-muted-foreground">ספרו לנו מה אתם אוהבים</p>
      </div>

      <div>
        <Label className="mb-3 block">סגנון נסיעה (אפשר לבחור כמה)</Label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {travelStyleOptions?.map((opt: any) => {
            const isSelected = styles?.includes(opt?.value ?? '')
            return (
              <button
                key={opt?.value}
                type="button"
                onClick={() => toggleStyle(opt?.value ?? '')}
                className={`flex items-center gap-3 p-4 rounded-lg border-2 transition-all text-sm font-medium ${
                  isSelected
                    ? 'border-primary bg-primary/10 text-primary shadow-sm'
                    : 'border-border hover:border-primary/40 hover:bg-muted/50'
                }`}
              >
                <opt.icon className="h-5 w-5 shrink-0" />
                {opt?.label}
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <Label htmlFor="specialRequests" className="mb-1.5 block">בקשות מיוחדות</Label>
        <Textarea
          id="specialRequests"
          placeholder="יש לכם בקשות מיוחדות? אלרגיות למזון, העדפות תזונתיות, אירועים מיוחדים..."
          value={form?.specialRequests ?? ''}
          onChange={(e: any) => updateForm({ specialRequests: e?.target?.value ?? '' })}
          rows={4}
        />
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          <ArrowRight className="ml-2 h-4 w-4" />
          חזרה
        </Button>
        <Button onClick={onNext}>
          <ArrowLeft className="ml-2 h-4 w-4" />
          המשך
        </Button>
      </div>
    </div>
  )
}
