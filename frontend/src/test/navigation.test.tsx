import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SoundProvider } from '@/contexts/SoundContext';
import { Sidebar } from '@/components/Sidebar';
import { ReviewQueue } from '@/pages/ReviewQueue';
import { Analytics } from '@/pages/Analytics';
import { Reports } from '@/pages/Reports';
import { Cameras } from '@/pages/Cameras';
import { Alerts } from '@/pages/Alerts';
import { Settings } from '@/pages/Settings';

describe('Sidebar Navigation Component', () => {
  it('renders all 4 uppercase section headers', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('MONITORING')).toBeInTheDocument();
    expect(screen.getByText('INCIDENTS')).toBeInTheDocument();
    expect(screen.getByText('SOURCES')).toBeInTheDocument();
    expect(screen.getByText('CONFIGURATION')).toBeInTheDocument();
  });

  it('renders all 9 navigation links with correct destinations', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    const expectedLinks = [
      { label: 'Live Dashboard', href: '/' },
      { label: 'Review Queue', href: '/review' },
      { label: 'Incident Search', href: '/search' },
      { label: 'Analytics', href: '/analytics' },
      { label: 'Reports', href: '/reports' },
      { label: 'Input / Output', href: '/feeder' },
      { label: 'Cameras', href: '/cameras' },
      { label: 'Alerts', href: '/alerts' },
      { label: 'Settings', href: '/settings' },
    ];

    for (const item of expectedLinks) {
      const link = screen.getByRole('link', { name: new RegExp(item.label, 'i') });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', item.href);
    }
  });

  it('renames Detection Studio to Input / Output and does not include legacy text', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    expect(screen.getByText('Input / Output')).toBeInTheDocument();
    expect(screen.queryByText(/Detection Studio/i)).not.toBeInTheDocument();
  });

  it('applies title tooltip attribute and ellipsis truncation styles to every nav item', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    const navLabels = [
      'Live Dashboard',
      'Review Queue',
      'Incident Search',
      'Analytics',
      'Reports',
      'Input / Output',
      'Cameras',
      'Alerts',
      'Settings',
    ];

    for (const label of navLabels) {
      const span = screen.getByText(label);
      expect(span).toBeInTheDocument();

      // Check title tooltip
      const link = span.closest('a');
      expect(link).toHaveAttribute('title', label);

      // Verify inline / CSS ellipsis truncation styles
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
    expect(reviewLink.className).toContain('text-cyan-400');
    expect(reviewLink.className).toContain('bg-cyan-500/10');

    const searchLink = screen.getByRole('link', { name: /Incident Search/i });
    expect(searchLink.className).toContain('text-slate-400');

    unmount();

    // Now test navigating to /settings
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <Sidebar />
      </MemoryRouter>
    );

    const settingsLink = screen.getByRole('link', { name: /Settings/i });
    expect(settingsLink.className).toContain('text-cyan-400');
  });

  it('displays alert count badge when alertCount > 0', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar alertCount={5} />
      </MemoryRouter>
    );

    const badge = screen.getByText('5');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-red-500/20');
  });

  it('truncates long labels with ellipsis without overflowing parent box', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Sidebar />
      </MemoryRouter>
    );

    const links = screen.getAllByRole('link');
    for (const link of links) {
      expect(link.className).toContain('min-w-0');
      const innerContainer = link.querySelector('div');
      expect(innerContainer?.className).toContain('min-w-0');
      expect(innerContainer?.className).toContain('overflow-hidden');
    }
  });
});

describe('Navigation Route Rendering', () => {
  it('renders ReviewQueue at route /review', async () => {
    render(
      <MemoryRouter initialEntries={['/review']}>
        <Routes>
          <Route path="/review" element={<ReviewQueue />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { level: 1, name: /Review Queue/i })).toBeInTheDocument();
    expect(screen.getByText(/Verify incident footage before initiating emergency response dispatch/i)).toBeInTheDocument();
  });

  it('renders Settings page at route /settings', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <SoundProvider>
            <MemoryRouter initialEntries={['/settings']}>
              <Routes>
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </MemoryRouter>
          </SoundProvider>
        </ThemeProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByRole('heading', { level: 1, name: /Control Room Settings/i })).toBeInTheDocument();
  });

  const placeholdersToTest = [
    { path: '/alerts', component: <Alerts />, title: 'Alerts & Notifications', phase: 'Phase 4' },
    { path: '/cameras', component: <Cameras />, title: 'Cameras', phase: 'Phase 5' },
    { path: '/analytics', component: <Analytics />, title: 'Surveillance Analytics', phase: 'Phase 6' },
    { path: '/reports', component: <Reports />, title: 'Incident Reports', phase: 'Phase 7' },
  ];

  for (const { path, component, title, phase } of placeholdersToTest) {
    it(`renders ${title} placeholder at route ${path}`, () => {
      render(
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={path} element={component} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.getByRole('heading', { level: 1, name: new RegExp(title, 'i') })).toBeInTheDocument();
      expect(screen.getByText(new RegExp(`Scheduled for ${phase}`, 'i'))).toBeInTheDocument();
      expect(screen.getByText(/human verification is required/i)).toBeInTheDocument();
    });
  }
});
