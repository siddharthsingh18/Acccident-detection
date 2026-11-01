import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModelScoreBreakdown } from '@/components/ModelScoreBreakdown';
import type { Incident } from '@/lib/api';

describe('ModelScoreBreakdown Component', () => {
  const baseIncident: Incident = {
    id: '1528_76',
    rowid: 1,
    camera_id: 1528,
    starting_frame_id: 76,
    city: 'Alexandria',
    district: 'Corniche',
    crash_time: '2026-11-01 12:00:00',
    thumbnail_url: '/media/thumbnails/1528_76.jpg',
    video_url: '/api/incidents/1528_76/video',
    model_scores: null,
  };

  it('always renders the mandatory human verification disclaimer', () => {
    render(<ModelScoreBreakdown incident={baseIncident} />);
    const disclaimer = screen.getByRole('note', { name: /Human verification required disclaimer/i });
    expect(disclaimer).toBeInTheDocument();
    expect(disclaimer).toHaveTextContent(/Model estimates, not confirmed facts/i);
    expect(disclaimer).toHaveTextContent(/Human verification required/i);
  });

  it('renders legacy placeholder when model_scores is null or undefined', () => {
    const { rerender } = render(<ModelScoreBreakdown incident={baseIncident} />);
    expect(screen.getByTestId('no-model-scores')).toHaveTextContent(
      'No model details were recorded for this incident.'
    );

    rerender(<ModelScoreBreakdown incident={null} />);
    expect(screen.getByTestId('no-model-scores')).toHaveTextContent(
      'No model details were recorded for this incident.'
    );
  });

  it('renders complete breakdown table with agreement, policy, scores, and chips', () => {
    const incidentWithScores: Incident = {
      ...baseIncident,
      model_scores: {
        policy: 'majority',
        threshold: 0.6,
        decision: true,
        scorers: [
          {
            name: 'vif_svm',
            score: 0.88,
            fired: true,
            calibrated: true,
            available: true,
            latency_ms: 12.5,
          },
          {
            name: 'convae',
            score: 0.72,
            fired: true,
            calibrated: false,
            available: true,
            latency_ms: 32.1,
          },
          {
            name: 'resnet_onnx',
            score: 0.35,
            fired: false,
            calibrated: false,
            available: false,
            latency_ms: null,
          },
        ],
      },
    };

    render(<ModelScoreBreakdown incident={incidentWithScores} />);

    // Agreement summary and policy rule
    expect(screen.getByTestId('agreement-summary')).toHaveTextContent(
      '2 of 2 available models flagged this'
    );
    expect(screen.getByTestId('policy-rule')).toHaveTextContent('Rule: majority, threshold 0.60');

    // Scorer rows
    expect(screen.getByTestId('scorer-row-vif_svm')).toBeInTheDocument();
    expect(screen.getByTestId('scorer-row-convae')).toBeInTheDocument();
    expect(screen.getByTestId('scorer-row-resnet_onnx')).toBeInTheDocument();

    // Model labels
    expect(screen.getByText('Violent Flows (VIF+SVM)')).toBeInTheDocument();
    expect(screen.getByText('ConvAE Spatio-Temporal')).toBeInTheDocument();

    // Verdict text chips (not color alone)
    const flaggedChips = screen.getAllByTestId('verdict-flagged');
    expect(flaggedChips).toHaveLength(2);
    expect(flaggedChips[0]).toHaveTextContent('Flagged');

    const unavailableChip = screen.getByTestId('verdict-unavailable');
    expect(unavailableChip).toHaveTextContent('Unavailable');

    // Uncalibrated tag
    expect(screen.getByText('uncalibrated')).toBeInTheDocument();

    // Progress bar accessible roles
    const progressBars = screen.getAllByRole('progressbar');
    expect(progressBars).toHaveLength(2); // for the 2 available scorers
    expect(progressBars[0]).toHaveAttribute('aria-valuenow', '88');
    expect(progressBars[1]).toHaveAttribute('aria-valuenow', '72');
  });

  it('renders "Not flagged" verdict when model score does not exceed threshold', () => {
    const unflaggedIncident: Incident = {
      ...baseIncident,
      model_scores: {
        policy: 'majority',
        threshold: 0.6,
        decision: false,
        scorers: [
          {
            name: 'vif_svm',
            score: 0.25,
            fired: false,
            calibrated: true,
            available: true,
          },
        ],
      },
    };

    render(<ModelScoreBreakdown incident={unflaggedIncident} />);
    const notFlagged = screen.getByTestId('verdict-not-flagged');
    expect(notFlagged).toHaveTextContent('Not flagged');
  });
});

