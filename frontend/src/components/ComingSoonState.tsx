import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Sparkles, ShieldAlert, ArrowRight } from 'lucide-react';

interface ComingSoonStateProps {
  title: string;
  section: string;
  description: string;
  icon: LucideIcon;
  phase: string;
  highlights?: string[];
}

export const ComingSoonState: React.FC<ComingSoonStateProps> = ({
  title,
  section,
  description,
  icon: Icon,
  phase,
  highlights = [],
}) => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <div className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold mb-1">
            {section}
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-3">
            <Icon className="w-6 h-6 text-cyan-400" />
            <span>{title}</span>
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            Scheduled for {phase}
          </span>
        </div>
      </div>

      {/* Decision Support Disclaimer */}
      <div className="bg-slate-900/40 border border-slate-800/60 rounded-lg p-3 text-xs text-slate-400 flex items-center gap-2.5">
        <ShieldAlert className="w-4 h-4 text-cyan-400 shrink-0" />
        <span>
          <strong>Operational Notice:</strong> Argus is engineered strictly as an assisted decision support platform. Human verification is required for all surveillance outcomes.
        </span>
      </div>

      {/* Main Empty State Card */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/30 p-8 sm:p-12 text-center max-w-2xl mx-auto space-y-6 shadow-xl shadow-black/20">
        <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center mx-auto text-cyan-400 shadow-[0_0_24px_rgba(6,182,212,0.15)]">
          <Icon className="w-8 h-8" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold text-slate-100">{title} Module</h2>
          <p className="text-sm text-slate-400 leading-relaxed max-w-lg mx-auto">
            {description}
          </p>
        </div>

        {highlights.length > 0 && (
          <div className="pt-4 border-t border-slate-800/60 text-left">
            <div className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              Planned Capabilities ({phase})
            </div>
            <ul className="space-y-2">
              {highlights.map((highlight, index) => (
                <li
                  key={index}
                  className="text-xs text-slate-300 flex items-start gap-2 bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/40"
                >
                  <ArrowRight className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                  <span>{highlight}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="pt-2 text-xs text-slate-500 font-mono">
          Route active and verified · Component placeholder ready for {phase} implementation
        </div>
      </div>
    </div>
  );
};
