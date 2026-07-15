import './globals.css'
import { Providers } from '@/components/Providers'
import AuthProvider from '@/components/AuthProvider'
import MainLayout from '@/components/MainLayout'

export const metadata = {
  title: 'PAAIM — Policy-Aware Agentic Intelligence Manager',
  description: 'Decide what matters on the factory floor, and prove why.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {/* Outside MainLayout: it gates the app and attaches the tenant token
              to every API call, so it must wrap the chrome as well as the page. */}
          <AuthProvider>
            <MainLayout>{children}</MainLayout>
          </AuthProvider>
        </Providers>
      </body>
    </html>
  )
}
