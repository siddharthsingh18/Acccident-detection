import { describe, it, expect } from 'vitest';
import {
  ModelScoresSchema,
  ModelsStatusResponseSchema,
  ScorerResultSchema,
} from '@/lib/modelsContract';

describe('modelsContract Zod Schemas', () => {
  it('parses valid ScorerResult', () => {
    const valid = {
      name: 'vif_svm',
      score: 0.85,
      fired: true,
      calibrated: true,
      available: true,
      latency_ms: 12.4,
    };
    const parsed = ScorerResultSchema.parse(valid);
    expect(parsed.name).toBe('vif_svm');
    expect(parsed.score).toBe(0.85);
  });

  it('rejects scores exceeding 1.0 or below 0.0', () => {
    expect(() =>
      ScorerResultSchema.parse({
        name: 'vif_svm',
        score: 1.5,
        fired: true,
      })
    ).toThrow();

    expect(() =>
      ScorerResultSchema.parse({
        name: 'vif_svm',
        score: -0.1,
        fired: false,
      })
    ).toThrow();
  });

  it('parses valid ModelScores ensemble structure', () => {
    const valid = {
      policy: 'majority',
      threshold: 0.6,
      decision: true,
      scorers: [
        { name: 'vif_svm', score: 0.88, fired: true, calibrated: true },
        { name: 'convae', score: 0.72, fired: true, calibrated: false },
      ],
    };
    const parsed = ModelScoresSchema.parse(valid);
    expect(parsed.policy).toBe('majority');
    expect(parsed.decision).toBe(true);
    expect(parsed.scorers).toHaveLength(2);
  });

  it('rejects invalid policy enum', () => {
    const invalid = {
      policy: 'super_majority', // not in ('any' | 'all' | 'majority' | 'weighted')
      threshold: 0.6,
      decision: true,
      scorers: [],
    };
    expect(() => ModelScoresSchema.parse(invalid)).toThrow();
  });

  it('parses valid ModelsStatusResponse', () => {
    const valid = {
      policy: 'majority',
      degraded: false,
      scorers: [
        {
          name: 'vif_svm',
          available: true,
          version: '1.0.0',
          trained_on: 'Argus dataset',
          calibration_date: '2021-03-01',
          reason_unavailable: null,
        },
      ],
    };
    const parsed = ModelsStatusResponseSchema.parse(valid);
    expect(parsed.degraded).toBe(false);
    expect(parsed.scorers[0].version).toBe('1.0.0');
  });
});

