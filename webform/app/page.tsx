import { HeroSection } from './_components/hero-section'
import { FeaturesSection } from './_components/features-section'
import { HowItWorksSection } from './_components/how-it-works-section'
import { CTASection } from './_components/cta-section'
import { SiteHeader } from '@/components/site-header'
import { SiteFooter } from '@/components/site-footer'

export default function HomePage() {
  return (
    <>
      <SiteHeader />
      <main className="pt-16">
        <HeroSection />
        <FeaturesSection />
        <HowItWorksSection />
        <CTASection />
      </main>
      <SiteFooter />
    </>
  )
}
