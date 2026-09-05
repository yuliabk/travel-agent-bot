'use client'

import { FormData } from './booking-wizard'
import { Button } from '@/components/ui/button'
import { ArrowRight, Send, User, Mail, Phone, MapPin, Calendar, Users, Wallet, Heart, FileText, Plane } from 'lucide-react'

interface Props { form: FormData; updateForm: (partial: Partial<FormData>) => void; onBack: () => void; onSubmit: () => void }
export function StepSummary({ form, updateForm, onBack, onSubmit }: Props) {
  const items = [
    { icon: Plane, label: 'שדה המראה', value: form.originAirport },
    { icon: Plane, label: 'שדה נחיתה', value: form.destinationAirport },
    { icon: User, label: 'שם', value: form?.name ?? '' }, { icon: Mail, label: 'מייל', value: form?.email ?? '' }, { icon: Phone, label: 'טלפון', value: form?.phone ?? '' }, { icon: Plane, label: 'מוצא', value: form?.origin ?? '' }, { icon: MapPin, label: 'יעד', value: form?.destination ?? '' }, { icon: Calendar, label: 'תאריכים', value: `${form?.dateFrom ?? ''} - ${form?.dateTo ?? ''}` }, { icon: Users, label: 'נוסעים', value: `${form?.adults ?? 0} מבוגרים, ${form?.children ?? 0} ילדים${(form?.childAges ?? []).length ? ` (גילים: ${form.childAges.join(', ')})` : ''}` }, { icon: Wallet, label: 'תקציב', value: `${form?.budgetAmount ?? ''} ${form?.currency ?? 'ILS'}` }, { icon: Plane, label: 'סוג טיסה', value: form?.flightStops === 'nonstop' ? 'טיסות ישירות' : form?.flightStops === 'oneStop' ? 'עד עצירה אחת' : 'כל הטיסות' }, { icon: Heart, label: 'סגנון נסיעה', value: (form?.travelStyles ?? []).join(', ') || 'לא נבחר' },
  ]
  return (
    <div className="space-y-6">
      <div className="text-center mb-2"><h2 className="font-display text-xl font-semibold">סיכום הבקשה</h2><p className="text-sm text-muted-foreground">ודאו שהפרטים נכונים לפני יצירת טיוטת ה-AI</p></div>
      <div className="space-y-3">{items.map((item, i) => <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"><item.icon className="h-4 w-4 text-primary mt-0.5 shrink-0" /><div><span className="text-xs text-muted-foreground">{item.label}</span><p className="text-sm font-medium">{item.value || '—'}</p></div></div>)}{(form?.specialRequests ?? '').trim() && <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50"><FileText className="h-4 w-4 text-primary mt-0.5 shrink-0" /><div><span className="text-xs text-muted-foreground">בקשות מיוחדות</span><p className="text-sm font-medium">{form.specialRequests}</p></div></div>}</div>
      <label className="flex items-start gap-3 rounded-lg border border-border p-4 bg-muted/30 cursor-pointer"><input type="checkbox" checked={form?.consent ?? false} onChange={(e) => updateForm({ consent: e.target.checked })} className="mt-1 h-4 w-4 accent-[hsl(var(--primary))]" /><span className="text-sm leading-relaxed">אני מאשר/ת להשתמש בפרטים שמסרתי לצורך יצירת טיוטת תכנון נסיעה. הטיוטה נוצרת אוטומטית ודורשת אישור סוכן לפני שהיא נחשבת להצעה סופית.</span></label>
      <div className="flex justify-between"><Button variant="outline" onClick={onBack}><ArrowRight className="ml-2 h-4 w-4" />חזרה</Button><Button onClick={onSubmit} className="px-8" disabled={!form?.consent}><Send className="ml-2 h-4 w-4" />יצירת טיוטת AI</Button></div>
    </div>
  )
}
