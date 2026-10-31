import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';
import { Navbar } from '@/components/Navbar';
import { SoundProvider } from '@/contexts/SoundContext';
import { DemoProvider } from '@/contexts/DemoContext';
import { MemoryRouter } from 'react-router-dom';

function TestThemeConsumer() {
  const { theme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <button onClick={toggleTheme}>Toggle</button>
    </div>
  );
}

describe('ThemeContext & Navbar Controls', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = '';
  });

  it('defaults to dark mode and sets class on documentElement', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('current-theme').textContent).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
  });

  it('toggles to light mode and updates documentElement classes and localStorage', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    const toggleBtn = screen.getByRole('button', { name: /toggle/i });
    act(() => {
      fireEvent.click(toggleBtn);
    });

    expect(screen.getByTestId('current-theme').textContent).toBe('light');
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('argus-theme')).toBe('light');

    // Toggle back to dark
    act(() => {
      fireEvent.click(toggleBtn);
    });
    expect(screen.getByTestId('current-theme').textContent).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
    expect(localStorage.getItem('argus-theme')).toBe('dark');
  });

  it('Navbar controls: theme toggle button switches theme and audio controls work', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ThemeProvider>
            <SoundProvider>
              <DemoProvider>
                <Navbar />
              </DemoProvider>
            </SoundProvider>
          </ThemeProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Navbar has theme toggle button
    const themeBtn = screen.getByRole('button', { name: /toggle theme/i });
    expect(themeBtn).toBeInTheDocument();

    // Toggle theme to light via Navbar button
    act(() => {
      fireEvent.click(themeBtn);
    });
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('argus-theme')).toBe('light');

    // Toggle theme back to dark via Navbar button
    act(() => {
      fireEvent.click(themeBtn);
    });
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
    expect(localStorage.getItem('argus-theme')).toBe('dark');

    // Navbar has audio controls: mute toggle and volume slider
    const muteToggleBtn = screen.getByRole('button', { name: /mute sound alarms/i });
    expect(muteToggleBtn).toBeInTheDocument();

    const volumeSlider = screen.getByLabelText(/siren volume slider/i);
    expect(volumeSlider).toBeInTheDocument();

    act(() => {
      fireEvent.click(muteToggleBtn);
    });

    act(() => {
      fireEvent.change(volumeSlider, { target: { value: '0.6' } });
    });
    expect(localStorage.getItem('argus-volume')).toBe('0.6');
  });
});
