import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from '@/components/Sidebar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SoundProvider } from '@/contexts/SoundContext';
import { DemoProvider } from '@/contexts/DemoContext';
import { AlertProvider } from '@/contexts/AlertContext';

describe('Sidebar Navigation Component (Simplified Working Pages)', () => {
  it('renders exactly four navigation links in the required order', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(4);

    const expectedItems = [
      { label: 'Live Dashboard', href: '/' },
      { label: 'Input / Output', href: '/feeder' },
      { label: 'Incident Search', href: '/search' },
      { label: 'Review Queue', href: '/review' },
    ];

    expectedItems.forEach((expected, index) => {
      const link = links[index];
      expect(link).toHaveAttribute('href', expected.href);
      expect(link).toHaveAttribute('title', expected.label);
      expect(link).toHaveTextContent(expected.label);
    });
  });

  it('does NOT render removed section headers or placeholder entries', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    // Group labels must be gone
    expect(screen.queryByText('MONITORING')).not.toBeInTheDocument();
    expect(screen.queryByText('INCIDENTS')).not.toBeInTheDocument();
    expect(screen.queryByText('SOURCES')).not.toBeInTheDocument();
    expect(screen.queryByText('CONFIGURATION')).not.toBeInTheDocument();

    // Placeholder entries must be gone
    expect(screen.queryByText('Analytics')).not.toBeInTheDocument();
    expect(screen.queryByText('Reports')).not.toBeInTheDocument();
    expect(screen.queryByText('Cameras')).not.toBeInTheDocument();
    expect(screen.queryByText('Alerts')).not.toBeInTheDocument();
    expect(screen.queryByText('Settings')).not.toBeInTheDocument();
  });

  it('renders ARGUS / Surveillance Ops brand header', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('ARGUS')).toBeInTheDocument();
    expect(screen.getByText(/Surveillance Ops/i)).toBeInTheDocument();
  });

  it('applies title tooltip attribute and ellipsis truncation styles to every nav item', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    const navLabels = [
      'Live Dashboard',
      'Input / Output',
      'Incident Search',
      'Review Queue',
    ];

    for (const label of navLabels) {
      const span = screen.getByText(label);
      expect(span).toBeInTheDocument();

      const link = span.closest('a');
      expect(link).toHaveAttribute('title', label);

      expect(span).toHaveStyle({
        minWidth: '0px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      });
    }
  });

  it('applies active styling to the currently active route', () => {
    const { unmount } = render(
      <MemoryRouter initialEntries={['/review']}>
        <Sidebar />
      </MemoryRouter>
    );

    const reviewLink = screen.getByRole('link', { name: /Review Queue/i });
    expect(reviewLink.className).toContain('text-cyan-600');
    expect(reviewLink.className).toContain('bg-cyan-500/10');

    const searchLink = screen.getByRole('link', { name: /Incident Search/i });
    expect(searchLink.className).toContain('text-slate-600');

    unmount();

    // Test active state for Input / Output
    render(
      <MemoryRouter initialEntries={['/feeder']}>
        <Sidebar />
      </MemoryRouter>
    );

    const feederLink = screen.getByRole('link', { name: /Input \/ Output/i });
    expect(feederLink.className).toContain('text-cyan-600');
  });

  it('displays alert count badge on Live Dashboard when alertCount > 0', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar alertCount={7} />
      </MemoryRouter>
    );

    const badge = screen.getByText('7');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-red-500/20');
  });

  it('supports 360px viewport without overflow, keeping min-w-0 and ellipsis styles', () => {
    window.innerWidth = 360;
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(4);
    for (const link of links) {
      expect(link.className).toContain('min-w-0');
      const innerContainer = link.querySelector('div');
      expect(innerContainer?.className).toContain('min-w-0');
      expect(innerContainer?.className).toContain('overflow-hidden');
    }
  });
});

describe('Navigation Routes and Catch-All Redirects', () => {
  function renderWithProviders(initialRoute: string) {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    return render(
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <SoundProvider>
            <DemoProvider>
              <AlertProvider>
                <MemoryRouter initialEntries={[initialRoute]}>
                  <Routes>
                    <Route path="/" element={<div data-testid="page-dashboard">Dashboard View</div>} />
                    <Route path="/feeder" element={<div data-testid="page-feeder">Feeder View</div>} />
                    <Route path="/search" element={<div data-testid="page-search">Search View</div>} />
                    <Route path="/review" element={<div data-testid="page-review">Review View</div>} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </MemoryRouter>
              </AlertProvider>
            </DemoProvider>
          </SoundProvider>
        </ThemeProvider>
      </QueryClientProvider>
    );
  }

  it('redirects old /settings URL to "/"', () => {
    renderWithProviders('/settings');
    expect(screen.getByTestId('page-dashboard')).toBeInTheDocument();
    expect(screen.queryByTestId('page-feeder')).not.toBeInTheDocument();
  });

  it('redirects old /analytics URL to "/"', () => {
    renderWithProviders('/analytics');
    expect(screen.getByTestId('page-dashboard')).toBeInTheDocument();
  });

  it('redirects old /reports URL to "/"', () => {
    renderWithProviders('/reports');
    expect(screen.getByTestId('page-dashboard')).toBeInTheDocument();
  });

  it('redirects old /cameras URL to "/"', () => {
    renderWithProviders('/cameras');
    expect(screen.getByTestId('page-dashboard')).toBeInTheDocument();
  });

  it('redirects old /alerts URL to "/"', () => {
    renderWithProviders('/alerts');
    expect(screen.getByTestId('page-dashboard')).toBeInTheDocument();
  });

  it('redirects random unknown URLs to "/"', () => {
    renderWithProviders('/random-nonexistent-path-123');
    expect(screen.getByTestId('page-dashboard')).toBeInTheDocument();
  });

  it('renders working routes without redirecting', () => {
    const { unmount } = renderWithProviders('/review');
    expect(screen.getByTestId('page-review')).toBeInTheDocument();
    unmount();

    renderWithProviders('/feeder');
    expect(screen.getByTestId('page-feeder')).toBeInTheDocument();
  });
});
