import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DemoProvider, useDemo } from '@/contexts/DemoContext';
import { DevComponentShowcase } from '@/pages/DevComponentShowcase';
import { api } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: {
    getHealth: vi.fn(),
    getRecentIncidents: vi.fn(),
    getIncidents: vi.fn(),
    reviewIncident: vi.fn(),
    createFeed: vi.fn(),
  },
}));

function DemoConsumer() {
  const { isDemoMode, toggleDemoMode, demoAlert, triggerNextDemoAlert } = useDemo();
  return (
    <div>
      <div data-testid="demo-status">{isDemoMode ? 'active' : 'inactive'}</div>
      <button data-testid="toggle-btn" onClick={toggleDemoMode}>Toggle</button>
      <button data-testid="trigger-btn" onClick={triggerNextDemoAlert}>Trigger</button>
      {demoAlert && (
        <div data-testid="demo-alert-data">
          <span>{demoAlert.incident_id}</span>
          <span data-testid="demo-alert-policy">{demoAlert.model_scores?.policy}</span>
          <span data-testid="demo-alert-decision">{demoAlert.model_scores?.decision ? 'yes' : 'no'}</span>
        </div>
      )}
    </div>
  );
}

describe('Demo Mode & Component Showcase Fixtures', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('generates simulated alerts with realistic model_scores and NEVER makes database writes', () => {
    render(
      <DemoProvider>
        <DemoConsumer />
      </DemoProvider>
    );

    expect(screen.getByTestId('demo-status')).toHaveTextContent('inactive');

    // Trigger demo alerts
    const triggerBtn = screen.getByTestId('trigger-btn');
    act(() => {
      triggerBtn.click();
    });

    const alertData = screen.getByTestId('demo-alert-data');
    expect(alertData).toBeInTheDocument();
    expect(screen.getByTestId('demo-alert-policy')).toHaveTextContent(/majority|any/);

    // Verify zero API writes were called
    expect(api.reviewIncident).not.toHaveBeenCalled();
    expect(api.createFeed).not.toHaveBeenCalled();
  });

  it('renders DevComponentShowcase displaying all 5 states', () => {
    render(
      <MemoryRouter>
        <DevComponentShowcase />
      </MemoryRouter>
    );

    // Verify all 5 storybook states are rendered
    expect(screen.getByTestId('state-all-agree')).toBeInTheDocument();
    expect(screen.getByTestId('state-split-decision')).toBeInTheDocument();
    expect(screen.getByTestId('state-one-flagged')).toBeInTheDocument();
    expect(screen.getByTestId('state-degraded')).toBeInTheDocument();
    expect(screen.getByTestId('state-null-scores')).toBeInTheDocument();

    // Verify verification disclaimer is rendered across components
    const disclaimers = screen.getAllByText(/Human verification required/i);
    expect(disclaimers.length).toBeGreaterThan(0);
  });
});
