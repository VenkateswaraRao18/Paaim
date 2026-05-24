import './globals.css'
import { Providers } from '@/components/Providers'

export const metadata = {
  title: 'PAAIM Dashboard',
  description: 'Policy-Aware Agentic Intelligence Manager Dashboard',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
