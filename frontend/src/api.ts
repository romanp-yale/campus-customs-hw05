export type Role = 'Boss' | 'Inventory' | 'Accounting' | 'Facilities' | 'Customer Service';
export interface Ticket { id: number; type: string; requester: string; subject: string; status: string; notes: string | null; sku: string | null; size: string | null; qty: number | null; }
export interface Payment { id: number; ticket_id: number; kind: string; ref_id: number; obligation_date: string; amount: number; account: string; status: string; approved_by: string | null; }
export interface Purchase { id: number; ticket_id: number; vendor_id: number; sku: string; size: string; qty: number; unit_cost: number; status: string; received_qty?: number; }
export interface Entry { sequence: number; recorded_at_utc: string; run_id: string; event: string; role: Role | null; data: Record<string, unknown>; }
export interface Report { summary: string; outcome: string; next_actions?: string[]; }
export interface Job { run_id: string; ticket_id: number; status: string; error?: string; result?: { report: Report; usage?: { total_tokens: number; estimated_cost_usd: string | null } }; }
export interface Dashboard { tickets: Ticket[]; cash_accounts: { name: string; balance: number; date: string }[]; desk: { date_today: string }[]; payment_requests: Payment[]; purchase_orders: Purchase[]; runs: Job[]; }
export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API + path, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers }, signal: options?.signal || AbortSignal.timeout(20000) });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : `Request refused (${response.status}). Check the details and try again.`);
  return body as T;
}
export const post = <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) });
export const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
