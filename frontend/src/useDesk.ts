import { useCallback, useEffect, useRef, useState } from 'react';
import { request } from './api';
import type { Dashboard, Entry } from './api';

export function useDesk(ticketId: number) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [error, setError] = useState('');
  const [activityError, setActivityError] = useState('');
  const [updated, setUpdated] = useState<Date | null>(null);
  const mounted = useRef(true);
  const loading = useRef(false);
  const refresh = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      const data = await request<Dashboard>('/dashboard');
      if (mounted.current) { setDashboard(data); setUpdated(new Date()); setError(''); }
    } catch (error) { if (mounted.current) setError(error instanceof Error ? error.message : 'Could not connect to the backend.'); }
    finally { loading.current = false; }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 8000);
    return () => { mounted.current = false; window.clearInterval(timer); };
  }, [refresh]);
  useEffect(() => {
    let active = true;
    let cursor = 0;
    let timer: number;
    const controller = new AbortController();
    setEntries([]); setActivityError('');
    async function poll() {
      try {
        const data = await request<{ entries: Entry[]; next_sequence: number }>(`/activity?ticket_id=${ticketId}&include_test_runs=false&after=${cursor}&limit=500`, { signal: controller.signal });
        if (active) {
          cursor = data.next_sequence;
          setEntries(previous => [...new Map([...previous, ...data.entries].map(e => [e.sequence, e])).values()].slice(-1000));
          setActivityError('');
        }
      } catch (error) { if (active) setActivityError(error instanceof Error ? error.message : 'Activity unavailable.'); }
      if (active) timer = window.setTimeout(() => void poll(), 2000);
    }
    void poll();
    return () => { active = false; controller.abort(); window.clearTimeout(timer); };
  }, [ticketId]);
  return { dashboard, setDashboard, entries, error, activityError, updated, refresh };
}
