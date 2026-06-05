import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TisTru',
  description: 'AI-assisted public claim investigation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body suppressHydrationWarning={true}>{children}</body>
    </html>
  )
}
