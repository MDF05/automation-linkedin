import React from 'react';
import { clsx } from 'clsx';

export interface ProviderUsage {
  provider: string;
  total_tokens: number;
  cost_estimate_usd: number | string;
  limit?: number | null;
  usage_percent?: number | null;
  call_count: number;
}

export interface AIUsageChartProps {
  providers: ProviderUsage[];
  period_days?: number;
}

const PROVIDER_COLORS: Record<string, string> = {
  deepseek: 'bg-blue-500',
  groq: 'bg-purple-500',
  chatgpt_web: 'bg-green-500',
  claude_web: 'bg-orange-500',
  perplexity_web: 'bg-pink-500',
};

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export const AIUsageChart: React.FC<AIUsageChartProps> = ({
  providers,
  period_days = 30,
}) => {
  if (providers.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 text-center text-sm text-gray-400">
        Belum ada penggunaan AI dalam {period_days} hari terakhir.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">
        Penggunaan AI — {period_days} Hari Terakhir
      </h2>

      <div className="flex flex-col gap-4">
        {providers.map((p) => {
          const pct = p.usage_percent ?? 0;
          const barColor = PROVIDER_COLORS[p.provider] ?? 'bg-gray-400';
          const isWarning = pct >= 80;

          return (
            <div key={p.provider}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-700 capitalize">
                  {p.provider.replace('_', ' ')}
                </span>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>{fmtTokens(p.total_tokens)} token</span>
                  <span>${Number(p.cost_estimate_usd).toFixed(4)}</span>
                  <span>{p.call_count} panggilan</span>
                  {p.usage_percent != null && (
                    <span className={clsx('font-medium', isWarning ? 'text-red-600' : 'text-gray-600')}>
                      {p.usage_percent.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>

              {p.usage_percent != null && (
                <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all',
                      barColor,
                      isWarning && 'opacity-80',
                    )}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                    role="progressbar"
                    aria-valuenow={pct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${p.provider} usage ${pct.toFixed(1)}%`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
