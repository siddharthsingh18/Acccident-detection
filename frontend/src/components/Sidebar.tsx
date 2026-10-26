import { NavLink } from 'react-router-dom';
import { Radio, Search, Video, ShieldAlert } from 'lucide-react';

interface SidebarProps {
  alertCount?: number;
}

export function Sidebar({ alertCount = 0 }: SidebarProps) {
  const navItems = [
    {
      to: '/',
      label: 'Live Dashboard',
      icon: Radio,
      badge: alertCount > 0 ? alertCount : null,
    },
    {
      to: '/search',
      label: 'Incident Search',
      icon: Search,
    },
    {
      to: '/feeder',
      label: 'Camera Feeder',
      icon: Video,
    },
  ];

  return (
    <aside className="w-full md:w-64 bg-slate-950/70 border-r border-slate-800/80 p-4 flex md:flex-col justify-between shrink-0">
      <div className="w-full space-y-1">
        <div className="hidden md:block px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500 font-mono">
          Surveillance Nodes
        </div>

        <nav className="flex md:flex-col gap-1 w-full overflow-x-auto md:overflow-x-visible">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-[0_0_12px_rgba(6,182,212,0.15)]'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                  }`
                }
              >
                <div className="flex items-center gap-3">
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="whitespace-nowrap">{item.label}</span>
                </div>
                {item.badge && (
                  <span className="ml-2 px-1.5 py-0.5 text-xs font-mono font-bold rounded-full bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* System Footer Note */}
      <div className="hidden md:block pt-4 border-t border-slate-800/60">
        <div className="px-3 py-2 rounded-lg bg-slate-900/40 border border-slate-800/40 text-xs text-slate-500 flex items-center gap-2">
          <ShieldAlert className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span>Computer Vision v1.0 connected to Edge Nodes</span>
        </div>
      </div>
    </aside>
  );
}
