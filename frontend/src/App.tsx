import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SoundProvider } from '@/contexts/SoundContext';
import { Navbar } from '@/components/Navbar';
import { Sidebar } from '@/components/Sidebar';
import { LiveDashboard } from '@/pages/LiveDashboard';
import { IncidentSearch } from '@/pages/IncidentSearch';
import { CameraFeeder } from '@/pages/CameraFeeder';
import { useAlertSocket } from '@/hooks/useAlertSocket';

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

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-300">
      <Navbar />
      <div className="flex-1 flex flex-col md:flex-row">
        <Sidebar alertCount={alerts.length} />
        <main className="flex-1 p-4 md:p-8 overflow-y-auto max-w-7xl w-full mx-auto">
          <Routes>
            <Route path="/" element={<LiveDashboard />} />
            <Route path="/search" element={<IncidentSearch />} />
            <Route path="/feeder" element={<CameraFeeder />} />
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
          <BrowserRouter>
            <AppLayout />
          </BrowserRouter>
        </SoundProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
