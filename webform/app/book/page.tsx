import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'
import { BookingWizard } from './_components/booking-wizard'

export default function BookPage() {
  return <><SiteHeader /><main className="pt-24 pb-16 min-h-screen bg-muted/20"><div className="mx-auto max-w-[800px] px-4 sm:px-6"><div className="text-center mb-10"><h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mb-3">תכננו את הטיול <span className="text-primary">שלכם</span></h1><p className="text-muted-foreground text-lg">מלאו את הפרטים וקבלו טיוטת טיול מותאמת אישית</p></div><BookingWizard /></div></main><SiteFooter /></>
}
