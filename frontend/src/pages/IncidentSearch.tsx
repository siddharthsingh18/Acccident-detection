import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Search,
  Filter,
  Download,
  RotateCcw,
  Clock,
  Calendar,
  Camera,
  MapPin,
  ChevronRight,
  ArrowUpDown,
  AlertCircle,
  FileQuestion,
  Play
} from 'lucide-react';
import { api, type Incident, type IncidentFilters } from '@/lib/api';
import { IncidentVideoModal } from '@/components/IncidentVideoModal';

const EGYPTIAN_CITIES = [
  'All Cities',
  'Cairo',
  'Alexandria',
  'Gizah',
  'Shubra El-Kheima',
  'Port Said',
  'Suez',
  'Luxor',
  'Al-Mansura',
  'Tanta',
  'Asyut',
  'Ismailia',
  'Fayyum',
  'Zagazig',
  'Aswan',
  'Damietta',
  'Damanhur',
  'Al-Minya',
  'Beni Suef',
  'Qena',
  'Sohag',
  'Hurghada',
  'Shibin El Kom',
  'Banha',
  'Arish',
];

const searchFilterSchema = z
  .object({
    start_date: z.string().optional(),
    end_date: z.string().optional(),
    start_time: z.string().optional(),
    end_time: z.string().optional(),
    city: z.string().optional(),
    district: z.string().optional(),
  })
  .refine(
    (data) => {
      if (data.start_date && data.end_date) {
        return new Date(data.end_date) >= new Date(data.start_date);
      }
      return true;
    },
    {
      message: 'End date must be greater than or equal to start date',
      path: ['end_date'],
    }
  );

type SearchFormData = z.infer<typeof searchFilterSchema>;

type SortField = 'crash_time' | 'camera_id' | 'city' | 'id';
type SortOrder = 'asc' | 'desc';

export function IncidentSearch() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);

  // Sorting
  const [sortField, setSortField] = useState<SortField>('crash_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // React Hook Form initialized from URL search params
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SearchFormData>({
    resolver: zodResolver(searchFilterSchema),
    defaultValues: {
      start_date: searchParams.get('start_date') || '',
      end_date: searchParams.get('end_date') || '',
      start_time: searchParams.get('start_time') || '',
      end_time: searchParams.get('end_time') || '',
      city: searchParams.get('city') || '',
      district: searchParams.get('district') || '',
    },
  });

  // Fetch incidents matching filters
  const fetchResults = async (filters: IncidentFilters) => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.getIncidents(filters);
      setIncidents(res.items);
      setNextCursor(res.next_cursor ?? null);
      setHasMore(res.has_more);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to search incidents.');
      setIsLoading(false);
    }
  };

  // Run search when URL query parameters change
  useEffect(() => {
    const filters: IncidentFilters = {
      start_date: searchParams.get('start_date') || undefined,
      end_date: searchParams.get('end_date') || undefined,
      start_time: searchParams.get('start_time') || undefined,
      end_time: searchParams.get('end_time') || undefined,
      city: searchParams.get('city') || undefined,
      district: searchParams.get('district') || undefined,
      limit: 20,
    };
    fetchResults(filters);
  }, [searchParams]);

  const onSubmit = (data: SearchFormData) => {
    const params = new URLSearchParams();
    if (data.start_date) params.set('start_date', data.start_date);
    if (data.end_date) params.set('end_date', data.end_date);
    if (data.start_time) params.set('start_time', data.start_time);
    if (data.end_time) params.set('end_time', data.end_time);
    if (data.city && data.city !== 'All Cities') params.set('city', data.city);
    if (data.district) params.set('district', data.district);
    setSearchParams(params);
  };

  const handleRecentClick = async () => {
    reset({
      start_date: '',
      end_date: '',
      start_time: '',
      end_time: '',
      city: '',
      district: '',
    });
    setSearchParams(new URLSearchParams());
    try {
      setIsLoading(true);
      setError(null);
      const recent = await api.getRecentIncidents();
      setIncidents(recent);
      setHasMore(false);
      setNextCursor(null);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load recent incidents.');
      setIsLoading(false);
    }
  };

  const handleExportCsv = () => {
    const filters: IncidentFilters = {
      start_date: searchParams.get('start_date') || undefined,
      end_date: searchParams.get('end_date') || undefined,
      start_time: searchParams.get('start_time') || undefined,
      end_time: searchParams.get('end_time') || undefined,
      city: searchParams.get('city') || undefined,
      district: searchParams.get('district') || undefined,
    };
    window.location.href = api.getExportUrl(filters);
  };

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const sortedIncidents = useMemo(() => {
    return [...incidents].sort((a, b) => {
      let comparison = 0;
      if (sortField === 'crash_time') {
        comparison = a.crash_time.localeCompare(b.crash_time);
      } else if (sortField === 'camera_id') {
        comparison = a.camera_id - b.camera_id;
      } else if (sortField === 'city') {
        comparison = (a.city || '').localeCompare(b.city || '');
      } else if (sortField === 'id') {
        comparison = a.id.localeCompare(b.id);
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [incidents, sortField, sortOrder]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Search className="w-6 h-6 text-cyan-400" />
            Surveillance Records Archive
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Query historical accident telemetry with cross-camera temporal and regional filters.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCsv}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-slate-200 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800 rounded-lg transition"
          >
            <Download className="w-4 h-4 text-cyan-400" />
            Export CSV
          </button>
          <button
            onClick={handleRecentClick}
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-slate-200 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800 rounded-lg transition"
          >
            <RotateCcw className="w-4 h-4 text-emerald-400" />
            Recent (10)
          </button>
        </div>
      </div>

      {/* Filter Form Panel */}
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
            {/* Start Date */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-cyan-400" />
                Start Date
              </label>
              <input
                type="date"
                {...register('start_date')}
                className="w-full px-3 py-2 text-xs font-mono rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition"
              />
            </div>

            {/* End Date */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-cyan-400" />
                End Date
              </label>
              <input
                type="date"
                {...register('end_date')}
                className="w-full px-3 py-2 text-xs font-mono rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition"
              />
              {errors.end_date && (
                <span className="text-[10px] text-red-400 mt-1 block">{errors.end_date.message}</span>
              )}
            </div>

            {/* Start Time */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-cyan-400" />
                Start Time
              </label>
              <input
                type="time"
                step="1"
                {...register('start_time')}
                className="w-full px-3 py-2 text-xs font-mono rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition"
              />
            </div>

            {/* End Time */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-cyan-400" />
                End Time
              </label>
              <input
                type="time"
                step="1"
                {...register('end_time')}
                className="w-full px-3 py-2 text-xs font-mono rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition"
              />
            </div>

            {/* City */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                City
              </label>
              <select
                {...register('city')}
                className="w-full px-3 py-2 text-xs rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition"
              >
                {EGYPTIAN_CITIES.map((c) => (
                  <option key={c} value={c === 'All Cities' ? '' : c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* District */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5 text-cyan-400" />
                District
              </label>
              <input
                type="text"
                placeholder="e.g. District 13"
                {...register('district')}
                className="w-full px-3 py-2 text-xs rounded-lg bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500 transition"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="submit"
              className="inline-flex items-center gap-2 px-5 py-2 text-xs font-semibold text-slate-950 bg-cyan-400 hover:bg-cyan-300 rounded-lg shadow-md transition"
            >
              <Search className="w-3.5 h-3.5" />
              Search Archive
            </button>
          </div>
        </form>
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-4 animate-pulse">
          <div className="h-6 bg-slate-800 rounded w-1/4" />
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-12 bg-slate-800 rounded" />
            ))}
          </div>
        </div>
      )}

      {/* Error Banner */}
      {!isLoading && error && (
        <div className="p-6 rounded-xl border border-red-500/30 bg-red-950/20 text-center max-w-md mx-auto">
          <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <h3 className="text-base font-medium text-white mb-1">Search Error</h3>
          <p className="text-xs text-slate-400">{error}</p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && sortedIncidents.length === 0 && (
        <div className="p-12 rounded-xl border border-slate-800 bg-slate-900/40 text-center max-w-md mx-auto">
          <FileQuestion className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-white mb-1">No Matching Incidents</h3>
          <p className="text-xs text-slate-400">
            No collision events found matching the specified temporal and regional parameters.
          </p>
        </div>
      )}

      {/* Results Table */}
      {!isLoading && !error && sortedIncidents.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/80 text-xs text-slate-400 border-b border-slate-800 uppercase tracking-wider font-mono">
                <tr>
                  <th className="px-4 py-3.5">Footage</th>
                  <th
                    className="px-4 py-3.5 cursor-pointer hover:text-cyan-400 transition"
                    onClick={() => toggleSort('id')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Incident ID</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3.5 cursor-pointer hover:text-cyan-400 transition"
                    onClick={() => toggleSort('camera_id')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Camera</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3.5 cursor-pointer hover:text-cyan-400 transition"
                    onClick={() => toggleSort('crash_time')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Crash Timestamp</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3.5 cursor-pointer hover:text-cyan-400 transition"
                    onClick={() => toggleSort('city')}
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Location</span>
                      <ArrowUpDown className="w-3 h-3" />
                    </div>
                  </th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {sortedIncidents.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedIncident(item)}
                    className="group hover:bg-slate-800/50 cursor-pointer transition"
                  >
                    {/* Thumbnail */}
                    <td className="px-4 py-3 w-28">
                      <div className="relative w-24 aspect-video rounded overflow-hidden bg-black border border-slate-800">
                        <img
                          src={item.thumbnail_url}
                          alt={`Thumbnail ${item.id}`}
                          loading="lazy"
                          className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = '/media/thumbnails/fallback';
                          }}
                        />
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/40">
                          <Play className="w-4 h-4 text-cyan-400 fill-cyan-400" />
                        </div>
                      </div>
                    </td>

                    {/* ID */}
                    <td className="px-4 py-3 font-mono font-medium text-cyan-400 text-xs">
                      #{item.id}
                    </td>

                    {/* Camera */}
                    <td className="px-4 py-3 font-mono text-white text-xs">
                      <span className="flex items-center gap-1.5">
                        <Camera className="w-3.5 h-3.5 text-slate-500" />
                        {item.camera_id}
                      </span>
                    </td>

                    {/* Crash Time */}
                    <td className="px-4 py-3 font-mono text-slate-300 text-xs">
                      {item.crash_time}
                    </td>

                    {/* Location */}
                    <td className="px-4 py-3 text-xs text-slate-300">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-red-400 shrink-0" />
                        <span>
                          {item.city || 'Unknown'}, {item.district || 'Unassigned'}
                        </span>
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedIncident(item);
                        }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-cyan-400 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 rounded-lg transition"
                      >
                        <Play className="w-3 h-3 fill-cyan-400" />
                        Play Footage
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="px-5 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs text-slate-400">
            <span>
              Showing <strong className="text-white">{sortedIncidents.length}</strong> incident records
            </span>

            {hasMore && nextCursor !== null && (
              <button
                onClick={() => {
                  const filters: IncidentFilters = {
                    start_date: searchParams.get('start_date') || undefined,
                    end_date: searchParams.get('end_date') || undefined,
                    start_time: searchParams.get('start_time') || undefined,
                    end_time: searchParams.get('end_time') || undefined,
                    city: searchParams.get('city') || undefined,
                    district: searchParams.get('district') || undefined,
                    limit: 20,
                    cursor: nextCursor,
                  };
                  fetchResults(filters);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-white transition"
              >
                <span>Load More Records</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Video Modal */}
      <IncidentVideoModal
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
      />
    </div>
  );
}
