import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
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

describe('ThemeContext & Navbar Theme Toggle', () => {
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

  it('Navbar theme toggle button switches theme on click', () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <SoundProvider>
            <DemoProvider>
              <Navbar />
            </DemoProvider>
          </SoundProvider>
        </ThemeProvider>
      </MemoryRouter>
    );

    const themeToggleBtn = screen.getByRole('button', { name: /toggle theme/i });
    expect(themeToggleBtn).toBeInTheDocument();
    expect(themeToggleBtn).toHaveAttribute('title', 'Switch to light mode');

    // Click to switch to light mode
    act(() => {
      fireEvent.click(themeToggleBtn);
    });
    expect(themeToggleBtn).toHaveAttribute('title', 'Switch to dark mode');
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    // Click again to switch back to dark mode
    act(() => {
      fireEvent.click(themeToggleBtn);
    });
    expect(themeToggleBtn).toHaveAttribute('title', 'Switch to light mode');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
  });
});
