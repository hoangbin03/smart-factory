import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/providers';
import { Sidebar } from '@/components/layout/sidebar';
import { TopBar } from '@/components/layout/topbar';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'Smart Software Factory',
  description: 'AI-driven software production platform.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={inter.variable}>
        <Providers>
          <div className="app-shell">
            <Sidebar />
            <div className="app-main">
              <TopBar />
              <main className="page-scroll">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
