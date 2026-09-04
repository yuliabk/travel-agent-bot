import { DM_Sans, Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { ThemeProvider } from '@/components/theme-provider'
import { Toaster } from '@/components/ui/sonner'
import { ChunkLoadErrorHandler } from '@/components/chunk-load-error-handler'
import { GoogleAnalytics } from '@/components/google-analytics'
import type { Metadata } from 'next'

export const dynamic = 'force-dynamic'

const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-sans' })
const jakartaSans = Plus_Jakarta_Sans({ subsets: ['latin'], variable: '--font-display' })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'סוכן נסיעות AI — תכנון הטיול המושלם',
  description: 'שירות תכנון טיולים חכם מבוסס בינה מלאכותית. קבלו תוכנית טיול מותאמת אישית תוך דקות.',
  icons: {
    icon: '/favicon.svg',
    shortcut: '/favicon.svg',
  },
  openGraph: {
    title: 'סוכן נסיעות AI — תכנון הטיול המושלם',
    description: 'שירות תכנון טיולים חכם מבוסס בינה מלאכותית',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
  },
  metadataBase: new URL(process.env.NEXTAUTH_URL ?? 'http://localhost:3000'),
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="he" dir="rtl" suppressHydrationWarning>
      <head>
        <script src="https://apps.abacus.ai/chatllm/appllm-lib.js" />
      </head>
      <body className={`${dmSans.variable} ${jakartaSans.variable} ${jetbrainsMono.variable} font-sans`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Toaster />
          <ChunkLoadErrorHandler />
        </ThemeProvider>
        <GoogleAnalytics />
      </body>
    </html>
  )
}
