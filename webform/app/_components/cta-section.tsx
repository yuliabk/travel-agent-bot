'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Plane, ArrowLeft } from 'lucide-react'
import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'

export function CTASection() {
  const { ref, inView } = useInView({ triggerOnce: true, threshold: 0.2 })

  return (
    <section className="py-20 sm:py-28 relative overflow-hidden" ref={ref}>
      <div className="absolute inset-0 -z-10">
        <Image
          src="https://images.pexels.com/photos/16089227/pexels-photo-16089227.jpeg?cs=srgb&dl=pexels-oleksandra-zelena-495851763-16089227.jpg&fm=jpg"
          alt="נוף הרים עם אגם בשקיעה"
          fill
          className="object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/50 to-black/60" />
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={inView ? { opacity: 1, scale: 1 } : {}}
        transition={{ duration: 0.6 }}
        className="relative z-10 mx-auto max-w-[1200px] px-4 sm:px-6 text-center"
      >
        <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-white tracking-tight mb-6">
          מוכנים לטיול הבא?
        </h2>
        <p className="text-white/80 text-lg max-w-xl mx-auto mb-10">
          השאירו את השאר לסוכן החכם שלנו — תוך דקות תקבלו תוכנית טיול מותאמת אישית.
        </p>
        <Button asChild size="lg" className="text-base px-10 py-6 rounded-xl shadow-lg">
          <Link href="/book">
            <Plane className="ml-2 h-5 w-5" />
            תכננו את הטיול שלכם עכשיו
          </Link>
        </Button>
      </motion.div>
    </section>
  )
}
