'use client'

import { useState, useEffect } from 'react'

export function FooterYear() {
  const [year, setYear] = useState(2026)

  useEffect(() => {
    setYear(new Date().getFullYear())
  }, [])

  return <>{year}</>
}
