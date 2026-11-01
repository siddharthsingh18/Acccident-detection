import {
  ShieldAlert,
  AlertCircle,
  Check,
  HelpCircle,
  Cpu,
} from 'lucide-react';
import type { Incident } from '@/lib/api';
import {
  formatScore,
  scorerLabel,
  agreementSummary,
} from '@/lib/modelFormatters';

interface ModelScoreBreakdownProps {
  incident: Incident | null | undefined;
  className?: string;
}

export function ModelScoreBreakdown({
  incident,
  className = '',
}: ModelScoreBreakdownProps) {
  const modelScores = incident?.model_scores;

  return (
    <div
      data-testid="model-score-breakdown"
      className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/70 p-4 space-y-3.5 shadow-sm transition-colors duration-200 ${className}`}
    >
      {/* Mandatory Human Verification Disclaimer */}
      <div
        role="note"
        aria-label="Human verification required disclaimer"
        className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-800 dark:text-amber-200 text-xs"
      >
        <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <strong className="font-semibold">Model estimates, not confirmed facts.</strong>{' '}
          <span className="text-amber-700 dark:text-amber-300">Human verification required.</span>
        </div>
      </div>

      {/* Header and Summary */}
      {!modelScores || !modelScores.scorers || modelScores.scorers.length === 0 ? (
        <div
          data-testid="no-model-scores"
          className="p-3 text-center rounded-lg bg-slate-100 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/80 text-xs text-slate-600 dark:text-slate-400"
        >
          No model details were recorded for this incident.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 pb-2 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-cyan-600 dark:text-cyan-400 shrink-0" />
              <span
                data-testid="agreement-summary"
                className="text-xs font-semibold text-slate-900 dark:text-white"
              >
                {agreementSummary(modelScores)}
              </span>
            </div>
            <div
              data-testid="policy-rule"
              className="text-[11px] font-mono text-slate-500 dark:text-slate-400"
            >
              Rule:{' '}
              <span className="text-slate-700 dark:text-slate-200 font-medium">
                {modelScores.policy}
              </span>
              , threshold{' '}
              <span className="text-slate-700 dark:text-slate-200 font-medium">
                {modelScores.threshold.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Model Scorers Table */}
          <div className="overflow-x-auto">
            <table
              className="w-full text-left text-xs border-collapse"
              aria-label="Model scoring breakdown"
            >
              <thead>
                <tr className="border-b border-slate-200/80 dark:border-slate-800/80 text-[10px] uppercase font-mono text-slate-500">
                  <th scope="col" className="pb-1.5 pr-2">Scorer</th>
                  <th scope="col" className="pb-1.5 px-2">Score</th>
                  <th scope="col" className="pb-1.5 pl-2 text-right">Verdict</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {modelScores.scorers.map((scorer) => {
                  const meta = scorerLabel(scorer.name);
                  const scoreVal = scorer.score;
                  const percentage = Math.round(Math.max(0, Math.min(1, scoreVal)) * 100);

                  return (
                    <tr
                      key={scorer.name}
                      data-testid={`scorer-row-${scorer.name}`}
                      className="group hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                    >
                      {/* Name & Metadata */}
                      <td className="py-2.5 pr-2 align-middle">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium text-slate-800 dark:text-slate-200">
                            {meta.label}
                          </span>
                          {!scorer.calibrated && scorer.available && (
                            <span
                              className="px-1.5 py-0.2 rounded text-[10px] font-mono font-medium bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30"
                              title="Uncalibrated score: raw model confidence"
                            >
                              uncalibrated
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight mt-0.5 line-clamp-1">
                          {meta.description}
                        </div>
                      </td>

                      {/* Score Bar & Value */}
                      <td className="py-2.5 px-2 align-middle min-w-[120px]">
                        {scorer.available ? (
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-[11px] font-mono">
                              <span className="font-semibold text-slate-900 dark:text-slate-100">
                                {formatScore(scoreVal)}
                              </span>
                              {scorer.latency_ms !== null && scorer.latency_ms !== undefined && (
                                <span className="text-[10px] text-slate-400">
                                  {scorer.latency_ms.toFixed(0)}ms
                                </span>
                              )}
                            </div>
                            <div
                              role="progressbar"
                              aria-valuenow={percentage}
                              aria-valuemin={0}
                              aria-valuemax={100}
                              aria-label={`${meta.label} confidence score`}
                              className="w-full h-1.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden"
                            >
                              <div
                                style={{ width: `${percentage}%` }}
                                className={`h-full rounded-full transition-all duration-300 ${
                                  scorer.fired
                                    ? 'bg-red-500 dark:bg-red-400'
                                    : 'bg-cyan-500 dark:bg-cyan-400'
                                }`}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-[11px] font-mono text-slate-400 italic">
                            No score
                          </span>
                        )}
                      </td>

                      {/* Verdict Text Chip */}
                      <td className="py-2.5 pl-2 align-middle text-right whitespace-nowrap">
                        {scorer.available ? (
                          scorer.fired ? (
                            <span
                              data-testid="verdict-flagged"
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-red-500/15 text-red-700 dark:text-red-300 border border-red-500/30"
                            >
                              <AlertCircle className="w-3 h-3 text-red-600 dark:text-red-400" />
                              <span>Flagged</span>
                            </span>
                          ) : (
                            <span
                              data-testid="verdict-not-flagged"
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                            >
                              <Check className="w-3 h-3 text-slate-500 dark:text-slate-400" />
                              <span>Not flagged</span>
                            </span>
                          )
                        ) : (
                          <span
                            data-testid="verdict-unavailable"
                            title={scorer.reason_unavailable || 'Model unavailable for this feed'}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30 cursor-help"
                          >
                            <HelpCircle className="w-3 h-3 text-amber-600 dark:text-amber-400" />
                            <span>Unavailable</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
