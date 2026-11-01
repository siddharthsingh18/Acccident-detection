import { z } from 'zod';

export const ScorerResultSchema = z.object({
  name: z.string(),
  score: z.number().min(0).max(1),
  fired: z.boolean(),
  calibrated: z.boolean().default(false),
  available: z.boolean().default(true),
  latency_ms: z.number().nullable().optional(),
  reason_unavailable: z.string().nullable().optional(),
});

export const ModelScoresSchema = z.object({
  policy: z.enum(['any', 'all', 'majority', 'weighted']),
  threshold: z.number().min(0).max(1),
  decision: z.boolean(),
  scorers: z.array(ScorerResultSchema),
});

export const ScorerStatusSchema = z.object({
  name: z.string(),
  available: z.boolean(),
  version: z.string(),
  trained_on: z.string(),
  calibration_date: z.string().nullable().optional(),
  reason_unavailable: z.string().nullable().optional(),
});

export const ModelsStatusResponseSchema = z.object({
  policy: z.enum(['any', 'all', 'majority', 'weighted']),
  scorers: z.array(ScorerStatusSchema),
  degraded: z.boolean(),
});

export type ScorerResult = z.infer<typeof ScorerResultSchema>;
export type ModelScores = z.infer<typeof ModelScoresSchema>;
export type ScorerStatus = z.infer<typeof ScorerStatusSchema>;
export type ModelsStatusResponse = z.infer<typeof ModelsStatusResponseSchema>;
