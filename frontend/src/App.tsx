import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SoundProvider } from '@/contexts/SoundContext';
import { DemoProvider, useDemo } from '@/contexts/DemoContext';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { LiveDashboard } from '@/pages/LiveDashboard';
import { ReviewQueue } from '@/pages/ReviewQueue';
import { IncidentSearch } from '@/pages/IncidentSearch';
import { Analytics } from '@/pages/Analytics';
import { Reports } from '@/pages/Reports';
import { CameraFeeder } from '@/pages/CameraFeeder';
import { Cameras } from '@/pages/Cameras';
import { Alerts } from '@/pages/Alerts';
import { Settings } from '@/pages/Settings';
import { useAlertSocket } from '@/hooks/useAlertSocket';
import { Sparkles } from 'lucide-react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function AppLayout() {
  const { alerts } = useAlertSocket();
  const { isDemoMode } = useDemo();
  const location = useLocation();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-300">
      <Navbar />

      {/* Demo Mode Banner */}
      {isDemoMode && (
        <div className="bg-amber-500/10 border-b border-amber-500/30 px-4 py-2 text-center text-xs text-amber-300 flex items-center justify-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
          <span>
            <strong>DEMO MODE ACTIVE:</strong> Generating simulated incident alerts without contacting or modifying the real surveillance database.
          </span>
        </div>
      )}

      <div className="flex-1 flex flex-col md:flex-row">
        <Sidebar alertCount={alerts.length} />
        <main
          key={location.pathname}
          className="page-transition flex-1 p-4 md:p-8 overflow-y-auto max-w-7xl w-full mx-auto"
        >
          <Routes>
            <Route path="/" element={<LiveDashboard />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/search" element={<IncidentSearch />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/feeder" element={<CameraFeeder />} />
            <Route path="/cameras" element={<Cameras />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <SoundProvider>
          <DemoProvider>
            <BrowserRouter>
              <AppLayout />
            </BrowserRouter>
          </DemoProvider>
        </SoundProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
