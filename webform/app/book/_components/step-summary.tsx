'use client'

import { FormData } from './booking-wizard'
import { Button } from '@/components/ui/button'
import { ArrowRight, Send, User, Mail, Phone, MapPin, Calendar, Users, Wallet, Heart, FileText, Plane } from 'lucide-react'

interface Props {
  form: FormData
  onBack: () => void
  onSubmit: () => void
}

export function StepSummary({ form, onBack, onSubmit }: Props) {
  const items = [
    { icon: User, label: 'שם', value: form?.name ?? '' },
    { icon: Mail, label: 'מייל', value: form?.email ?? '' },
    { icon: Phone, label: 'טלפון', value: form?.phone ?? '' },
    { icon: MapPin, label: 'יעד', value: form?.destination ?? '' },
    { icon: Calendar, label: 'תאריכים', value: `${form?.dateFrom ?? ''} — ${form?.dateTo ?? ''}` },
    { icon: Users, label: 'נוסעים', value: `${form?.adults ?? 0} מבוגרים, ${form?.children ?? 0} ילדים` },
    { icon: Wallet, label: 'תקציב', value: form?.budget ?? '' },
    { icon: Plane, label: 'סוג טיסה', value: form?.flightStops === 'nonstop' ? 'טיסות ישירות' : form?.flightStops === 'oneStop' ? 'עד עצירה אחת' : 'כל הטיסות' },
    { icon: Heart, label: 'סגנון נסיעה', value: (form?.travelStyles ?? [])?.join(', ') || 'לא נבחר' },
  ]

  return (
    <div className="space-y-6">
      <div className="text-center mb-2">
        <h2 className="font-display text-xl font-semibold">סיכום הבקשה</h2>
        <p className="text-sm text-muted-foreground">ודאו שהפרטים נכונים לפני השליחה</p>
      </div>

      <div className="space-y-3">
        {items?.map((item: any, i: number) => (
          <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
            <item.icon className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <div>
              <span className="text-xs text-muted-foreground">{item?.label}</span>
              <p className="text-sm font-medium">{item?.value || '—'}</p>
            </div>
          </div>
        ))}

        {(form?.specialRequests ?? '').trim() && (
          <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
            <FileText className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <div>
              <span className="text-xs text-muted-foreground">בקשות מיוחדות</span>
              <p className="text-sm font-medium">{form?.specialRequests}</p>
            </div>
          </div>
        )}
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          <ArrowRight className="ml-2 h-4 w-4" />
          חזרה
        </Button>
        <Button onClick={onSubmit} className="px-8">
          <Send className="ml-2 h-4 w-4" />
          שלחו לסוכן
        </Button>
      </div>
    </div>
  )
}
