'use client'

import { Brain, Clock, Globe, Shield, Sparkles, Users } from 'lucide-react'
import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'

const features = [
  { icon: Brain, title: 'בינה מלאכותית מתקדמת', description: 'הסוכן שלנו מנתח אלפי יעדים, מסלולים וטיפים כדי ליצור חוויה מושלמת.' },
  { icon: Clock, title: 'תכנון מהיר', description: 'קבלו תוכנית טיול מפורטת תוך דקות ספורות, בלי להמתין ימים.' },
  { icon: Globe, title: 'כל היעדים בעולם', description: 'חופשות הים, הרים, ערים אורופאיות — אנחנו מכסים הכל.' },
  { icon: Users, title: 'מותאם לכל קבוצה', description: 'זוגות, משפחות, קבוצות גדולות — כל טיול מעוצב למידה.' },
  { icon: Sparkles, title: 'הצעות ייחודיות', description: 'המלצות שאף אחד לא ידע עליהן — מסעדות, אטרקציות, חוויות.' },
  { icon: Shield, title: 'אמינות ופרטיות', description: 'המידע שלכם מאובטח. אנו לא משתפים אותו עם צד שלישי.' },
]

export function FeaturesSection() {
  const { ref, inView } = useInView({ triggerOnce: true, threshold: 0.1 })
  return (
    <section className="py-20 sm:py-28 bg-muted/40" ref={ref}>
      <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mb-4">למה <span className="text-primary">סוכן נסיעות AI</span>?</h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">שילוב של טכנולוגיה מתקדמת עם ניסיון מעמיק בנסיעות</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.div key={feature.title} initial={{ opacity: 0, y: 20 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.5, delay: i * 0.1 }} className="bg-card rounded-xl p-6 shadow-[var(--shadow-md)] hover:shadow-[var(--shadow-lg)] transition-shadow">
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4"><feature.icon className="h-6 w-6 text-primary" /></div>
              <h3 className="font-display font-semibold text-lg mb-2">{feature.title}</h3>
              <p className="text-muted-foreground text-sm leading-relaxed">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
