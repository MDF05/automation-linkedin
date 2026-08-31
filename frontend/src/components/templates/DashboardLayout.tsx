import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { clsx } from 'clsx';
import {
  LayoutDashboard,
  PenSquare,
  MessageSquare,
  Briefcase,
  Calendar,
  History,
  Settings,
} from 'lucide-react';
import { DeviceStatusBar } from '../organisms/DeviceStatusBar';
import { useDeviceStatus } from '../../hooks/useDeviceStatus';

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { href: '/', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
  { href: '/studio', label: 'Studio', icon: <PenSquare size={18} /> },
  { href: '/engage', label: 'Engage', icon: <MessageSquare size={18} /> },
  { href: '/jobs', label: 'Jobs', icon: <Briefcase size={18} /> },
  { href: '/schedule', label: 'Scheduler', icon: <Calendar size={18} /> },
  { href: '/history', label: 'History', icon: <History size={18} /> },
  { href: '/settings', label: 'Settings', icon: <Settings size={18} /> },
];

export interface DashboardLayoutProps {
  children: React.ReactNode;
  title?: string;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children, title }) => {
  const router = useRouter();
  const deviceStatus = useDeviceStatus();

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="flex w-56 flex-shrink-0 flex-col border-r border-gray-200 bg-white">
        {/* Logo */}
        <div className="flex h-14 items-center border-b border-gray-200 px-4">
          <span className="text-base font-semibold text-blue-600">LinkedIn Bot</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3" aria-label="Main navigation">
          <ul className="space-y-0.5">
            {NAV_ITEMS.map((item) => {
              const active = router.pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={clsx(
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                      active
                        ? 'bg-blue-50 text-blue-700'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                    )}
                    aria-current={active ? 'page' : undefined}
                  >
                    <span className={active ? 'text-blue-600' : 'text-gray-400'}>{item.icon}</span>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6 gap-4">
          {title && <h1 className="text-base font-semibold text-gray-900">{title}</h1>}
          <div className="ml-auto w-72">
            <DeviceStatusBar status={deviceStatus} />
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
};
