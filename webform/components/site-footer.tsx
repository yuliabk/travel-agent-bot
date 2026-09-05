import { Plane } from 'lucide-react'
import Link from 'next/link'
import { FooterYear } from './footer-year'
export function SiteFooter(){return <footer className="no-print border-t border-border bg-muted/30"><div className="mx-auto max-w-[1200px] px-4 sm:px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4"><div className="flex items-center gap-2 text-sm text-muted-foreground"><Plane className="h-4 w-4 text-primary"/><span>סוכן נסיעות AI &copy; <FooterYear/></span></div><div className="flex items-center gap-6 text-sm"><Link href="/" className="text-muted-foreground hover:text-foreground">דף הבית</Link><Link href="/book" className="text-muted-foreground hover:text-foreground">הזמנת טיול</Link></div></div></footer>}
