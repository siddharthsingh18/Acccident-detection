import type { ModelScores } from './modelsContract';

export interface ScorerInfo {
  label: string;
  shortName: string;
  description: string;
}

const KNOWN_SCORERS: Record<string, ScorerInfo> = {
  vif_svm: {
    label: 'Violent Flows (VIF+SVM)',
    shortName: 'VIF+SVM',
    description: 'Kinetic flow variance spikes across motion vector regions',
  },
  convae: {
    label: 'ConvAE Spatio-Temporal',
    shortName: 'ConvAE',
    description: 'Unsupervised autoencoder irregularity reconstruction error',
  },
  resnet_onnx: {
    label: 'ResNet-50 Classifier (ONNX)',
    shortName: 'ResNet ONNX',
    description: 'Pre-trained deep convolutional visual impact classification',
  },
};

/**
 * Clamps score to [0.00, 1.00] and formats to exactly two decimal places.
 * Returns 'N/A' for null, undefined, or NaN inputs.
 */
export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return 'N/A';
  }
  const clamped = Math.max(0, Math.min(1, score));
  return clamped.toFixed(2);
}

/**
 * Maps an internal model identifier to operator-facing title, short pill name, and description.
 */
export function scorerLabel(name: string): ScorerInfo {
  const normalized = name.toLowerCase().trim();
  if (KNOWN_SCORERS[normalized]) {
    return KNOWN_SCORERS[normalized];
  }

  // Format custom names nicely (e.g. 'yolo_impact' -> 'Yolo Impact')
  const formatted = normalized
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

  return {
    label: formatted,
    shortName: formatted.split(' ')[0] || normalized,
    description: 'Supplemental crash scoring model',
  };
}

/**
 * Produces an honest, accessible agreement summary string across available models.
 */
export function agreementSummary(modelScores: ModelScores | null | undefined): string {
  if (!modelScores || !modelScores.scorers || modelScores.scorers.length === 0) {
    return 'No model details recorded for this incident';
  }

  const scorers = modelScores.scorers;
  const available = scorers.filter(s => s.available);
  const totalAvailable = available.length;
  const totalConfigured = scorers.length;

  if (totalAvailable === 0) {
    return 'No models were available for this inference';
  }

  const firedCount = available.filter(s => s.fired).length;

  if (totalAvailable < totalConfigured) {
    if (firedCount === 1) {
      return `Only 1 of ${totalAvailable} available models flagged this`;
    }
    return `${firedCount} of ${totalAvailable} available models flagged this`;
  }

  if (firedCount === 1 && totalAvailable > 1) {
    return `Only 1 of ${totalAvailable} models flagged this`;
  }

  return `${firedCount} of ${totalAvailable} models flagged this`;
}
