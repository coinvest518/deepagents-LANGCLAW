import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FDWA LangClaw — Deep Agents Command Center',
  description: 'FDWA Futuristic Digital Wealth Agency — LangClaw AI Command Center',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="scanlines" />
        {children}
      </body>
    </html>
  )
}
