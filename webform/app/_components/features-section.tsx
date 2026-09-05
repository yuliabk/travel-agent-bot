'use client'

import { Brain, Clock, Globe, Shield, Sparkles, Users } from 'lucide-react'
import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'

const features = [
  { icon: Brain, title: 'בינה מלאכותית מתקדמת', description: 'הסוכן מסייע לבנות טיוטת מסלול מותאמת לדרישות שתמסרו.' },
  { icon: Clock, title: 'תכנון מהיר', description: 'מקבלים טיוטת תכנון ראשונית במהירות, ולאחר מכן ניתן לדייק ולאשר אותה.' },
  { icon: Globe, title: 'יעדים ברחבי העולם', description: 'ערים, טבע, חופים וטיולים משולבים לפי ההעדפות שלכם.' },
  { icon: Users, title: 'מותאם להרכב הנוסעים', description: 'הטיוטה מתחשבת במספר המבוגרים, הילדים וההעדפות שהוזנו.' },
  { icon: Sparkles, title: 'טיוטה מותאמת אישית', description: 'מסלול והמלצות שמותאמים לפרטי הבקשה, עם סימון ברור של מידע חסר.' },
  { icon: Shield, title: 'פרטיות ובקרה', description: 'המידע מעובד רק לצורך הטיפול בבקשה ובהתאם לבקרות המערכת והספקים המאושרים.' },
]

export function FeaturesSection() {
  const { ref, inView } = useInView({ triggerOnce: true, threshold: 0.1 })
  return <section className="py-20 sm:py-28 bg-muted/40" ref={ref}><div className="mx-auto max-w-[1200px] px-4 sm:px-6"><div className="text-center mb-16"><h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mb-4">למה <span className="text-primary">סוכן נסיעות AI</span>?</h2><p className="text-muted-foreground text-lg max-w-2xl mx-auto">שילוב של תכנון אוטומטי עם בקרה אנושית לפני הצעה סופית</p></div><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">{features.map((feature,i)=><motion.div key={feature.title} initial={{opacity:0,y:20}} animate={inView?{opacity:1,y:0}:{}} transition={{duration:.5,delay:i*.1}} className="bg-card rounded-xl p-6 shadow-[var(--shadow-md)] hover:shadow-[var(--shadow-lg)] transition-shadow"><div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4"><feature.icon className="h-6 w-6 text-primary"/></div><h3 className="font-display font-semibold text-lg mb-2">{feature.title}</h3><p className="text-muted-foreground text-sm leading-relaxed">{feature.description}</p></motion.div>)}</div></div></section>
}
