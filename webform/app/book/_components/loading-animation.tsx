'use client'

import { motion } from 'framer-motion'
import { Plane, Globe, MapPin } from 'lucide-react'

export function LoadingAnimation() {
  return (
    <div className="bg-card rounded-xl shadow-[var(--shadow-md)] p-12 text-center">
      <div className="relative w-32 h-32 mx-auto mb-8">
        {/* Orbiting globe */}
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-0 flex items-center justify-center"
        >
          <Globe className="h-20 w-20 text-primary/20" />
        </motion.div>
        {/* Flying plane */}
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-0"
        >
          <Plane className="h-8 w-8 text-primary absolute -top-2 left-1/2 -translate-x-1/2 rotate-[-45deg]" />
        </motion.div>
        {/* Pulsing pin */}
        <motion.div
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 1.5, repeat: Infinity }}
          className="absolute inset-0 flex items-center justify-center"
        >
          <MapPin className="h-10 w-10 text-primary" />
        </motion.div>
      </div>

      <h3 className="font-display text-xl font-semibold mb-3">הסוכן החכם מתכנן את הטיול שלכם...</h3>
      <p className="text-muted-foreground">זה עשוי לקחת כמה רגעים</p>

      <motion.div
        className="mt-6 h-1.5 bg-muted rounded-full overflow-hidden max-w-xs mx-auto"
      >
        <motion.div
          className="h-full bg-primary rounded-full"
          animate={{ x: ['-100%', '100%'] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          style={{ width: '40%' }}
        />
      </motion.div>
    </div>
  )
}
