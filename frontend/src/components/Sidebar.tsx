import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Radio,
  Search,
  Video,
  ShieldAlert,
  ClipboardCheck,
  BarChart3,
  FileText,
  Camera,
  Bell,
  Settings,
} from 'lucide-react';

interface SidebarProps {
  alertCount?: number;
}

export interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: number | null;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export function Sidebar({ alertCount = 0 }: SidebarProps) {
  const sections: NavSection[] = [
    {
      title: 'MONITORING',
      items: [
        {
          to: '/',
          label: 'Live Dashboard',
          icon: Radio,
          badge: alertCount > 0 ? alertCount : null,
        },
        {
          to: '/review',
          label: 'Review Queue',
          icon: ClipboardCheck,
        },
      ],
    },
    {
      title: 'INCIDENTS',
      items: [
        {
          to: '/search',
          label: 'Incident Search',
          icon: Search,
        },
        {
          to: '/analytics',
          label: 'Analytics',
          icon: BarChart3,
        },
        {
          to: '/reports',
          label: 'Reports',
          icon: FileText,
        },
      ],
    },
    {
      title: 'SOURCES',
      items: [
        {
          to: '/feeder',
          label: 'Input / Output',
          icon: Video,
        },
        {
          to: '/cameras',
          label: 'Cameras',
          icon: Camera,
        },
      ],
    },
    {
      title: 'CONFIGURATION',
      items: [
        {
          to: '/alerts',
          label: 'Alerts',
          icon: Bell,
        },
        {
          to: '/settings',
          label: 'Settings',
          icon: Settings,
        },
      ],
    },
  ];

  return (
    <aside className="w-full md:w-64 bg-slate-950/70 border-b md:border-b-0 md:border-r border-slate-800/80 p-3 md:p-4 flex flex-col justify-between shrink-0">
      <div className="w-full space-y-3">
        <nav
          aria-label="Main Navigation"
          className="flex md:flex-col gap-3 md:gap-2.5 w-full overflow-x-auto md:overflow-x-visible pb-2 md:pb-0 scrollbar-thin"
        >
          {sections.map((section) => (
            <div key={section.title} className="flex flex-col gap-0.5 shrink-0 md:shrink min-w-0">
              <div className="px-3 pt-1.5 pb-1 text-[10px] md:text-[11px] font-semibold uppercase tracking-wider text-slate-500 font-mono select-none">
                {section.title}
              </div>

              <div className="flex md:flex-col gap-1 min-w-0">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      title={item.label}
                      className={({ isActive }) =>
                        `flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-all min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 ${
                          isActive
                            ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)]'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                        }`
                      }
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1 overflow-hidden">
                        <Icon className="w-4 h-4 shrink-0" />
                        <span
                          className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap block flex-1"
                          style={{
                            minWidth: 0,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {item.label}
                        </span>
                      </div>
                      {item.badge && (
                        <span className="ml-2 px-1.5 py-0.5 text-xs font-mono font-bold rounded-full bg-red-500/20 text-red-400 border border-red-500/40 shrink-0 animate-pulse">
                          {item.badge}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* System Footer Note */}
      <div className="hidden md:block pt-4 border-t border-slate-800/60 mt-4">
        <div className="px-3 py-2 rounded-lg bg-slate-900/40 border border-slate-800/40 text-xs text-slate-500 flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span className="truncate" title="Computer Vision v1.0 connected to Edge Nodes">
            Computer Vision v1.0 connected
          </span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
