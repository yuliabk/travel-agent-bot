'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Plane, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'

export function HeroSection() {
  return (
    <section className="relative min-h-[85vh] flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0">
        <Image src="https://images.pexels.com/photos/38321094/pexels-photo-38321094.jpeg?cs=srgb&dl=pexels-sarimphotos-38321094.jpg&fm=jpg" alt="חוף טרופי עם מים צלולים" fill className="object-cover" priority />
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/70" />
      </div>
      <div className="relative z-10 mx-auto max-w-[1200px] px-4 sm:px-6 text-center">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <div className="inline-flex items-center gap-2 bg-white/15 backdrop-blur-md rounded-full px-4 py-2 mb-6 text-white/90 text-sm"><Sparkles className="h-4 w-4 text-amber-300" /><span>מונע על ידי בינה מלאכותית</span></div>
          <h1 className="font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold text-white tracking-tight leading-tight mb-6">תכננו את הטיול<br /><span className="text-transparent bg-clip-text bg-gradient-to-l from-amber-300 to-orange-400">המושלם שלכם</span></h1>
          <p className="text-lg sm:text-xl text-white/80 max-w-2xl mx-auto mb-10">סוכן הנסיעות החכם שלנו יבנה עבורכם תוכנית טיול מותאמת אישית, בהתבסס על ההעדפות והתקציב שלכם.</p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button asChild size="lg" className="text-base px-8 py-6 rounded-xl shadow-lg"><Link href="/book"><Plane className="ml-2 h-5 w-5" />התחילו לתכנן</Link></Button>
            <Button asChild variant="outline" size="lg" className="text-base px-8 py-6 rounded-xl bg-white/10 border-white/30 text-white hover:bg-white/20 hover:text-white"><Link href="#how-it-works">איך זה עובד?</Link></Button>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
