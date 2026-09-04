'use client'

import { FormData } from './booking-wizard'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { User, Mail, Phone, ArrowLeft } from 'lucide-react'
import { useState } from 'react'

interface Props {
  form: FormData
  updateForm: (partial: Partial<FormData>) => void
  onNext: () => void
}

export function StepPersonal({ form, updateForm, onNext }: Props) {
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const errs: Record<string, string> = {}
    if (!(form?.name ?? '').trim()) errs.name = 'נא הזינו שם מלא'
    if (!(form?.email ?? '').trim()) errs.email = 'נא הזינו כתובת מייל'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form?.email ?? '')) errs.email = 'כתובת מייל לא תקינה'
    if (!(form?.phone ?? '').trim()) errs.phone = 'נא הזינו מספר טלפון'
    setErrors(errs)
    return Object.keys(errs ?? {})?.length === 0
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-2">
        <h2 className="font-display text-xl font-semibold">פרטים אישיים</h2>
        <p className="text-sm text-muted-foreground">ספרו לנו קצת על עצמכם</p>
      </div>

      <div className="space-y-4">
        <div>
          <Label htmlFor="name" className="mb-1.5 block">שם מלא</Label>
          <div className="relative">
            <User className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              id="name"
              placeholder="ישראל ישראלי"
              value={form?.name ?? ''}
              onChange={(e: any) => updateForm({ name: e?.target?.value ?? '' })}
              className="pr-10"
              variant={errors?.name ? 'error' : 'default'}
            />
          </div>
          {errors?.name && <p className="text-destructive text-xs mt-1">{errors.name}</p>}
        </div>

        <div>
          <Label htmlFor="email" className="mb-1.5 block">כתובת מייל</Label>
          <div className="relative">
            <Mail className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              id="email"
              type="email"
              placeholder="example@email.com"
              dir="ltr"
              value={form?.email ?? ''}
              onChange={(e: any) => updateForm({ email: e?.target?.value ?? '' })}
              className="pr-10 text-left"
              variant={errors?.email ? 'error' : 'default'}
            />
          </div>
          {errors?.email && <p className="text-destructive text-xs mt-1">{errors.email}</p>}
        </div>

        <div>
          <Label htmlFor="phone" className="mb-1.5 block">מספר טלפון</Label>
          <div className="relative">
            <Phone className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              id="phone"
              type="tel"
              placeholder="050-1234567"
              dir="ltr"
              value={form?.phone ?? ''}
              onChange={(e: any) => updateForm({ phone: e?.target?.value ?? '' })}
              className="pr-10 text-left"
              variant={errors?.phone ? 'error' : 'default'}
            />
          </div>
          {errors?.phone && <p className="text-destructive text-xs mt-1">{errors.phone}</p>}
        </div>
      </div>

      <div className="flex justify-start">
        <Button onClick={() => validate() && onNext()} className="px-8">
          <ArrowLeft className="ml-2 h-4 w-4" />
          המשך
        </Button>
      </div>
    </div>
  )
}
