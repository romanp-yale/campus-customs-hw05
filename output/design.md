# Problem 8 — Campus Customs operations desk

## Layout and visual direction

The dashboard is an operations desk with a quiet charcoal/navy background, translucent layered panels, soft borders, and a restrained mint accent. It follows the workspace dark glassmorphism preference. A narrow navigation rail links to tickets, agents, activity, and approvals. The headline establishes the shop and the human's role; the overview row makes open/resolved counts, team status, pending decisions, and checking balance visible before any action.

A persistent ticket queue sits on the left. The selected ticket's facts and Run ticket control occupy the center. Agent cards follow immediately below, with the activity stream and human-review queue alongside one another beneath them. Approval requests cover the entire shop, because all tickets share cash. Each approval displays its own ticket number. This avoids hiding another ticket's obligations while a user investigates one ticket.

Ticket names, requester, SKU, size, quantity, notes, date, status, balance, and approval amounts all come from FastAPI/MCP database responses. The UI ships with no demo shop data. Unknown values show a dash or loading state. The shop date is desk.date_today; stream timestamps are separately displayed as local observation times.

## Agent presentation

Each of the five roles has a recognizable icon, initials, responsibility subtitle, and a restrained accent: Boss/mint, Inventory/blue, Accounting/amber, Facilities/violet, Customer Service/rose. Color accompanies text rather than replacing it. Every role is visible to make the team's structure clear, while unused specialists show Standing by and No contribution this run. The UI does not pretend all specialists participate in every ticket.

Working status follows actual role-specific audit activity during a running job. A small pulse identifies an active agent; completed AgentReports become expandable View contribution summaries. Reports preserve the agent's outcome and summary. Boss's final report and token/cost usage appear with the run result. A run completing does not imply a ticket is resolved: the stored ticket status determines resolution.

## Activity and tool evidence

The stream polls the append-only audit endpoint every two seconds, scoped to the selected ticket and then its most recent run. Offline model-test runs are excluded using server-side audit classification. Actions, agent text messages, delegations, and tool calls/results have distinct labels. All actions, Agent actions, and Tool usage filters support focused review. Tool calls show the exact tool name; expandable arguments and returned database evidence support inspection without filling the main stream with JSON. React renders database text as text, never injected HTML.

The dashboard snapshot refreshes every eight seconds through one MCP read, including tickets, checking cash, approval/purchase requests, and backend-session run status. It also refreshes after an approval or run request. Activity uses an incremental sequence cursor; old events are deduplicated, and the in-memory display is capped at 1,000 events. The audit file itself remains untouched. Polling cleans up timers and aborts stale ticket activity requests when selection changes.

## Resolved tickets and run states

Resolved tickets use a mint status badge and check mark, subdued text, and a retained queue position so the history remains reviewable. Their action reads Ticket resolved and is disabled. Open tickets retain an open status dot; selecting one adds a mint left edge and brighter panel border. The backend's actual status drives every resolved style. Failed runs produce a visible error and keep the stored ticket status. Awaiting human approval remains a distinct report outcome, not a false success.

Only one shop operation runs at a time. Run controls and human decisions are disabled while the backend reports a running job or the UI is submitting a mutation. Other tickets can still be selected and inspected. A running ticket is identified even if the user opens a different ticket.

## Checking balance and human approval

The checking balance is a prominent mint figure with a currency symbol and cents; it reflects cash_accounts rather than calculated sales or incoming money. The API refresh after approved payment supplies the new value. Connection failures preserve the last confirmed snapshot and identify it as stale, rather than replacing money with zero.

Each pending payment card shows the ticket, obligation reference, stored amount, account, and obligation date. Review payment expands the human-name field, an explicit amount-specific attestation, and Approve & pay / Reject controls. Approval sends only the decision and human name; stored server-side terms determine the amount. The UI never receives the private MCP approval secret. The backend's human-only atomic approval tool verifies sufficient cash and unchanged terms, records the payment, and updates the relevant obligation. Refusals remain visible.

Purchase cards label the existing unit-cost total as a planning estimate. Human confirmation requires a real quoted unit cost, human name, and supplier/quote attestation. An optional checkbox identifies goods covered by an already paid linked invoice; MCP verifies the coverage. Confirm purchase does not spend cash. Accounting subsequently prepares a separate payment request, which the human approves in the payment queue. Physically receiving goods remains a separate explicit human attestation through the existing CLI, not an invented automatic stock increase.

## Accessibility, responsive behavior, and errors

Controls use native buttons, inputs, labels, checkboxes, and disclosure elements. Keyboard focus rings are visible; selected ticket/filter buttons expose aria-pressed state; error banners use role=alert and action notifications use role=status. Agent/tool information has text labels in addition to icons and color. Reduced-motion preferences disable animation.

At narrower desktop sizes, the lower panels stack. Tablet layouts move tickets above the workspace; phones stack the ticket cards, use two-column agent cards, hide the narrow rail, and make the Run control full width. The browser check at a 375 CSS-pixel mobile viewport confirmed equal content and viewport widths, with no horizontal overflow. System-font fallbacks keep the UI usable if optional Google Fonts cannot load.

Backend connection, configuration, audit, and action errors are shown visibly with retry controls. The frontend defaults to http://localhost:8000; an optional VITE_API_URL can override it for local development. CORS already allows http://localhost:5173 and http://127.0.0.1:5173. Vite uses strict port 5173 so it does not silently move to a disallowed origin. No Portkey or approval key belongs in Vite environment variables.
