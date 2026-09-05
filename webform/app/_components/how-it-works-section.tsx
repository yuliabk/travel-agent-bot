'use client'

import Image from 'next/image'
import { motion } from 'framer-motion'
import { ClipboardList, Send, MapPin } from 'lucide-react'

const steps = [
  { icon: ClipboardList, number: '01', title: 'מלאו את השאלון', description: 'הזינו מוצא, יעד, תאריכים, הרכב נוסעים, תקציב והעדפות.' },
  { icon: Send, number: '02', title: 'שלחו את הבקשה', description: 'הבקשה עוברת למנוע Contract v1 שמייצר טיוטה בלי לבצע הזמנה או תשלום.' },
  { icon: MapPin, number: '03', title: 'קבלו טיוטת טיול', description: 'קבלו AI Draft לבדיקה. הצעה סופית דורשת אישור סוכן נסיעות.' },
]

export function HowItWorksSection() {
  return <section id="how-it-works" className="py-20 sm:py-28 relative overflow-hidden"><div className="absolute inset-0 -z-10"><Image src="https://images.pexels.com/photos/16002589/pexels-photo-16002589/free-photo-of-town-on-sea-shore.jpeg" alt="עיר חוף ים תיכונית" fill className="object-cover"/><div className="absolute inset-0 bg-background/90 backdrop-blur-sm"/></div><div className="mx-auto max-w-[1200px] px-4 sm:px-6"><div className="text-center mb-16"><h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mb-4">איך זה <span className="text-primary">עובד</span>?</h2><p className="text-muted-foreground text-lg max-w-2xl mx-auto">שלושה צעדים מטופס ועד טיוטה לבדיקת סוכן</p></div><div className="grid grid-cols-1 md:grid-cols-3 gap-8">{steps.map((step,i)=><motion.div key={step.number} initial={{opacity:0,y:30}} whileInView={{opacity:1,y:0}} viewport={{once:true,amount:0.1}} transition={{duration:.6,delay:i*.12}} className="text-center"><div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4"><step.icon className="h-7 w-7 text-primary"/></div><span className="font-mono text-3xl font-bold text-primary/30">{step.number}</span><h3 className="font-display font-semibold text-xl mt-2 mb-3">{step.title}</h3><p className="text-muted-foreground leading-relaxed">{step.description}</p></motion.div>)}</div></div></section>
}
