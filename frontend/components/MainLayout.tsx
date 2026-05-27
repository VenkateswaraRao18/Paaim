'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ReactNode } from 'react';

interface NavigationItem {
  href: string;
  label: string;
  icon: string;
  description: string;
}

const navigation: NavigationItem[] = [
  {
    href: '/dashboard',
    label: 'Dashboard',
    icon: '📊',
    description: 'Incident tracking & decisions',
  },
  {
    href: '/custom-agents',
    label: 'Custom Agents',
    icon: '⚡',
    description: 'No-code agent builder',
  },
  {
    href: '/audit',
    label: 'Audit Log',
    icon: '📋',
    description: 'Compliance & evidence trail',
  },
];

export default function MainLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  const isLandingPage = pathname === '/';

  if (isLandingPage) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation Header */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-3">
              <div className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                PAAIM
              </div>
              <div className="hidden sm:block text-sm text-gray-600">
                Manufacturing Intelligence
              </div>
            </Link>

            {/* Nav Items */}
            <div className="flex items-center gap-1">
              {navigation.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    }`}
                  >
                    <span className="hidden sm:inline">{item.icon} </span>
                    {item.label}
                  </Link>
                );
              })}
            </div>

            {/* Status Indicator */}
            <div className="flex items-center gap-2">
              <div className="hidden sm:flex items-center gap-2 px-3 py-2 bg-green-50 rounded-lg">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span className="text-sm font-medium text-green-700">Live</span>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-sm text-gray-600">
            <p>
              PAAIM v1.0 • Policy-Aware Agentic Intelligence Manager • Manufacturing
              Decision Orchestration
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
