import type { Metadata } from 'next'
import Script from 'next/script'
import PageviewBeacon from '../components/PageviewBeacon'
import './globals.css'
import './constants.css'

export const metadata: Metadata = {
  title: 'TisTru',
  description: 'AI-assisted public claim investigation',
  icons:{
    icon: '/tistru2.png',
  } 
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body suppressHydrationWarning={true}>
        {/* HF/Docker: start.sh writes this from runtime Space env (build-time NEXT_PUBLIC_* is often empty). */}
        <Script src="/runtime-config.js" strategy="beforeInteractive" />
        <PageviewBeacon />
        {children}
      </body>
    </html>
  )
}
