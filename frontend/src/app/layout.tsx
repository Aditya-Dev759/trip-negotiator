import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TripNegotiator - Multi-Agent Trip Planning',
  description: 'Plan trips through multi-agent AI negotiation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className="bg-slate-50 text-slate-900"
        style={{ ['--font-display' as any]: "'Plus Jakarta Sans', var(--font-sans)", ['--font-sans' as any]: "'Inter', -apple-system, sans-serif" }}
      >
        {children}
      </body>
    </html>
  )
}
