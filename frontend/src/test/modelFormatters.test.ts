import { describe, it, expect } from 'vitest';
import {
  formatScore,
  scorerLabel,
  agreementSummary,
} from '@/lib/modelFormatters';
import type { ModelScores } from '@/lib/modelsContract';

describe('modelFormatters', () => {
  describe('formatScore', () => {
    it('formats numbers to two decimal places', () => {
      expect(formatScore(0.854)).toBe('0.85');
      expect(formatScore(0.8)).toBe('0.80');
      expect(formatScore(0)).toBe('0.00');
      expect(formatScore(1)).toBe('1.00');
    });

    it('clamps out of range numbers between 0 and 1', () => {
      expect(formatScore(1.45)).toBe('1.00');
      expect(formatScore(-0.25)).toBe('0.00');
    });

    it('returns N/A for null, undefined, or NaN', () => {
      expect(formatScore(null)).toBe('N/A');
      expect(formatScore(undefined)).toBe('N/A');
      expect(formatScore(Number.NaN)).toBe('N/A');
    });
  });

  describe('scorerLabel', () => {
    it('returns rich descriptive metadata for known models', () => {
      const vif = scorerLabel('vif_svm');
      expect(vif.label).toBe('Violent Flows (VIF+SVM)');
      expect(vif.shortName).toBe('VIF+SVM');
      expect(vif.description).toContain('flow');

      const convae = scorerLabel('convae');
      expect(convae.label).toBe('ConvAE Spatio-Temporal');
      expect(convae.shortName).toBe('ConvAE');

      const onnx = scorerLabel('resnet_onnx');
      expect(onnx.label).toContain('ResNet');
      expect(onnx.shortName).toBe('ResNet ONNX');
    });

    it('gracefully formats unmapped model names', () => {
      const custom = scorerLabel('custom_detector');
      expect(custom.label).toBe('Custom Detector');
      expect(custom.shortName).toBe('Custom');
    });
  });

  describe('agreementSummary', () => {
    it('handles null and undefined modelScores', () => {
      expect(agreementSummary(null)).toBe('No model details recorded for this incident');
      expect(agreementSummary(undefined)).toBe('No model details recorded for this incident');
    });

    it('handles empty scorers array', () => {
      const emptyScores: ModelScores = {
        policy: 'majority',
        threshold: 0.6,
        decision: false,
        scorers: [],
      };
      expect(agreementSummary(emptyScores)).toBe('No model details recorded for this incident');
    });

    it('summarizes when all models are available and all fired', () => {
      const allFired: ModelScores = {
        policy: 'majority',
        threshold: 0.6,
        decision: true,
        scorers: [
          { name: 'vif_svm', score: 0.9, fired: true, calibrated: true, available: true },
          { name: 'convae', score: 0.8, fired: true, calibrated: false, available: true },
          { name: 'resnet_onnx', score: 0.7, fired: true, calibrated: false, available: true },
        ],
      };
      expect(agreementSummary(allFired)).toBe('3 of 3 models flagged this');
    });

    it('summarizes when only 1 of 3 models fired', () => {
      const oneFired: ModelScores = {
        policy: 'majority',
        threshold: 0.6,
        decision: false,
        scorers: [
          { name: 'vif_svm', score: 0.9, fired: true, calibrated: true, available: true },
          { name: 'convae', score: 0.2, fired: false, calibrated: false, available: true },
          { name: 'resnet_onnx', score: 0.3, fired: false, calibrated: false, available: true },
        ],
      };
      expect(agreementSummary(oneFired)).toBe('Only 1 of 3 models flagged this');
    });

    it('summarizes when no models fired', () => {
      const noneFired: ModelScores = {
        policy: 'majority',
        threshold: 0.6,
        decision: false,
        scorers: [
          { name: 'vif_svm', score: 0.1, fired: false, calibrated: true, available: true },
          { name: 'convae', score: 0.2, fired: false, calibrated: false, available: true },
        ],
      };
      expect(agreementSummary(noneFired)).toBe('0 of 2 models flagged this');
    });

    it('explicitly reports available count when some models were unavailable', () => {
      const partialAvailable: ModelScores = {
        policy: 'majority',
        threshold: 0.6,
        decision: true,
        scorers: [
          { name: 'vif_svm', score: 0.85, fired: true, calibrated: true, available: true },
          { name: 'convae', score: 0.75, fired: true, calibrated: false, available: true },
          { name: 'resnet_onnx', score: 0.0, fired: false, calibrated: false, available: false },
        ],
      };
      expect(agreementSummary(partialAvailable)).toBe('2 of 2 available models flagged this');
    });

    it('reports "Only 1 of N available" when 1 model fired with unavailable models present', () => {
      const oneAvailableFired: ModelScores = {
        policy: 'majority',
        threshold: 0.6,
        decision: false,
        scorers: [
          { name: 'vif_svm', score: 0.85, fired: true, calibrated: true, available: true },
          { name: 'convae', score: 0.3, fired: false, calibrated: false, available: true },
          { name: 'resnet_onnx', score: 0.0, fired: false, calibrated: false, available: false },
        ],
      };
      expect(agreementSummary(oneAvailableFired)).toBe('Only 1 of 2 available models flagged this');
    });

    it('handles edge case where 0 models were available', () => {
      const zeroAvailable: ModelScores = {
        policy: 'majority',
        threshold: 0.6,
        decision: false,
        scorers: [
          { name: 'vif_svm', score: 0, fired: false, calibrated: true, available: false },
          { name: 'convae', score: 0, fired: false, calibrated: false, available: false },
        ],
      };
      expect(agreementSummary(zeroAvailable)).toBe('No models were available for this inference');
    });
  });
});
