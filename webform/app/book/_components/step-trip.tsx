'use client'

import { FormData } from './booking-wizard'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { MapPin, Calendar, Users, Wallet, ArrowLeft, ArrowRight, Minus, Plus, Plane } from 'lucide-react'
import { useState } from 'react'

interface Props { form: FormData; updateForm: (partial: Partial<FormData>) => void; onNext: () => void; onBack: () => void }
const popularDestinations = ['יוון','פריז','רומא','ברצלונה','לונדון','ניו יורק','אמסטרדם','סנטוריני','באלי','מלדיבים','טוקיו','דובאי','איסלנד','קרואטיה','פראג','קנקון']
const flightStopsOptions: { value: 'any' | 'oneStop' | 'nonstop'; label: string }[] = [
  { value: 'any', label: 'כל הטיסות' }, { value: 'oneStop', label: 'עד עצירה אחת' }, { value: 'nonstop', label: 'טיסות ישירות' },
]

export function StepTrip({ form, updateForm, onNext, onBack }: Props) {
  const [errors, setErrors] = useState<Record<string,string>>({})
  const [showSuggestions, setShowSuggestions] = useState(false)
  const filteredDests = popularDestinations.filter((d) => d.includes(form?.destination ?? ''))
  const setChildren = (next: number) => { const count=Math.max(0,next); const ages=[...(form.childAges??[])]; while(ages.length<count) ages.push(0); updateForm({children:count,childAges:ages.slice(0,count)}) }
  const validate = () => {
    const errs: Record<string,string> = {}
    if (!(form.origin ?? '').trim()) errs.origin='נא הזינו נקודת מוצא'
    if (!(form.destination ?? '').trim()) errs.destination='נא הזינו יעד'
    if (!form.dateFrom) errs.dateFrom='נא בחרו תאריך התחלה'
    if (!form.dateTo) errs.dateTo='נא בחרו תאריך סיום'
    if (form.dateFrom && form.dateTo && form.dateTo < form.dateFrom) errs.dateTo='תאריך החזרה חייב להיות לאחר תאריך היציאה'
    const budget=Number(form.budgetAmount); if(!Number.isFinite(budget)||budget<=0) errs.budgetAmount='נא הזינו תקציב מספרי'
    if((form.childAges??[]).length!==(form.children??0)||(form.childAges??[]).some((age)=>age<0||age>17)) errs.childAges='נא הזינו גיל תקין עבור כל ילד'
    setErrors(errs); return Object.keys(errs).length===0
  }
  return <div className="space-y-6">
    <div className="text-center mb-2"><h2 className="font-display text-xl font-semibold">פרטי הטיול</h2><p className="text-sm text-muted-foreground">מאיפה יוצאים ולאן נוסעים?</p></div>
    <div className="space-y-4">
      <div><Label htmlFor="origin" className="mb-1.5 block">נקודת מוצא</Label><div className="relative"><Plane className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"/><Input id="origin" placeholder="לדוגמה: תל אביב, ישראל" value={form.origin} onChange={(e:any)=>updateForm({origin:e.target.value})} className="pr-10" variant={errors.origin?'error':'default'}/></div>{errors.origin&&<p className="text-destructive text-xs mt-1">{errors.origin}</p>}</div>
      <div className="relative"><Label htmlFor="destination" className="mb-1.5 block">יעד הנסיעה</Label><div className="relative"><MapPin className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"/><Input id="destination" placeholder="לדוגמה: יוון, פריז, רומא..." value={form.destination} onChange={(e:any)=>{updateForm({destination:e.target.value});setShowSuggestions(true)}} onFocus={()=>setShowSuggestions(true)} onBlur={()=>setTimeout(()=>setShowSuggestions(false),200)} className="pr-10" variant={errors.destination?'error':'default'}/></div>{showSuggestions&&form.destination.length>0&&filteredDests.length>0&&<div className="absolute z-20 top-full mt-1 w-full bg-popover rounded-lg shadow-lg border border-border max-h-48 overflow-auto">{filteredDests.map((d)=><button key={d} type="button" className="w-full text-right px-4 py-2 text-sm hover:bg-muted" onMouseDown={()=>{updateForm({destination:d});setShowSuggestions(false)}}>{d}</button>)}</div>}{errors.destination&&<p className="text-destructive text-xs mt-1">{errors.destination}</p>}</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div><Label htmlFor="dateFrom" className="mb-1.5 block">תאריך התחלה</Label><div className="relative"><Calendar className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"/><Input id="dateFrom" type="date" value={form.dateFrom} onChange={(e:any)=>updateForm({dateFrom:e.target.value})} className="pr-10" variant={errors.dateFrom?'error':'default'}/></div>{errors.dateFrom&&<p className="text-destructive text-xs mt-1">{errors.dateFrom}</p>}</div>
        <div><Label htmlFor="dateTo" className="mb-1.5 block">תאריך סיום</Label><div className="relative"><Calendar className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"/><Input id="dateTo" type="date" value={form.dateTo} onChange={(e:any)=>updateForm({dateTo:e.target.value})} className="pr-10" variant={errors.dateTo?'error':'default'}/></div>{errors.dateTo&&<p className="text-destructive text-xs mt-1">{errors.dateTo}</p>}</div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {[['מבוגרים','adults'],['ילדים','children']].map(([label,key])=><div key={key}><Label className="mb-1.5 block">{label}</Label><div className="flex items-center gap-3 bg-muted/50 rounded-lg p-3"><Users className="h-4 w-4 text-muted-foreground"/><Button type="button" variant="outline" size="icon-sm" onClick={()=>key==='adults'?updateForm({adults:Math.max(1,form.adults-1)}):setChildren(form.children-1)}><Minus className="h-3 w-3"/></Button><span className="font-semibold min-w-[2ch] text-center">{key==='adults'?form.adults:form.children}</span><Button type="button" variant="outline" size="icon-sm" onClick={()=>key==='adults'?updateForm({adults:form.adults+1}):setChildren(form.children+1)}><Plus className="h-3 w-3"/></Button></div></div>)}
      </div>
      {form.children>0&&<div><Label className="mb-2 block">גילי הילדים</Label><div className="grid grid-cols-2 sm:grid-cols-4 gap-3">{form.childAges.map((age,i)=><div key={i}><Label htmlFor={`child-age-${i}`} className="text-xs text-muted-foreground">ילד {i+1}</Label><Input id={`child-age-${i}`} type="number" min={0} max={17} value={age} onChange={(e:any)=>{const ages=[...form.childAges];ages[i]=Number(e.target.value);updateForm({childAges:ages})}}/></div>)}</div>{errors.childAges&&<p className="text-destructive text-xs mt-1">{errors.childAges}</p>}</div>}
      <div><Label className="mb-1.5 block">תקציב כולל משוער</Label><div className="grid grid-cols-[1fr_120px] gap-3"><div className="relative"><Wallet className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"/><Input id="budgetAmount" type="number" min={1} placeholder="לדוגמה: 8000" value={form.budgetAmount} onChange={(e:any)=>updateForm({budgetAmount:e.target.value})} className="pr-10" variant={errors.budgetAmount?'error':'default'}/></div><Select value={form.currency} onValueChange={(v:'ILS'|'USD'|'EUR'|'GBP')=>updateForm({currency:v})}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value="ILS">ILS ₪</SelectItem><SelectItem value="USD">USD $</SelectItem><SelectItem value="EUR">EUR €</SelectItem><SelectItem value="GBP">GBP £</SelectItem></SelectContent></Select></div>{errors.budgetAmount&&<p className="text-destructive text-xs mt-1">{errors.budgetAmount}</p>}</div>
      <div><Label className="mb-1.5 block">עצירות בטיסה</Label><div className="grid grid-cols-3 gap-2">{flightStopsOptions.map((opt)=>{const active=form.flightStops===opt.value;return <button key={opt.value} type="button" onClick={()=>updateForm({flightStops:opt.value})} className={`flex flex-col items-center gap-1 rounded-lg border p-3 text-center ${active?'border-primary bg-primary/5':'border-border bg-muted/50'}`}><Plane className={`h-4 w-4 ${active?'text-primary':'text-muted-foreground'}`}/><span className={`text-xs font-medium ${active?'text-primary':''}`}>{opt.label}</span></button>})}</div></div>
    </div>
    <div className="flex justify-between"><Button variant="outline" onClick={onBack}><ArrowRight className="ml-2 h-4 w-4"/>חזרה</Button><Button onClick={()=>validate()&&onNext()}><ArrowLeft className="ml-2 h-4 w-4"/>המשך</Button></div>
  </div>
}
