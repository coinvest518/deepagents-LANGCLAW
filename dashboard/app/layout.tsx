import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'DeepAgents Command Center',
  description: 'Tony Stark HUD — AI Agent Intelligence Dashboard',
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
