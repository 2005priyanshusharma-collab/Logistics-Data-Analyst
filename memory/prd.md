Logistics Data Analysis — Product Brief
Original problem statement
Build an internship-ready logistics analytics project for a fictional Kolkata freight trucking firm. Investigate a falling business metric, prove its drivers with shipment, route, vehicle and warehouse scan data, document hypotheses and statistical evidence, quantify the decline with a driver tree, separate seasonal events from structural trends, and provide an early-warning view. Deliver an analysis notebook, driver tree, hypothesis log and management root-cause memo in a bright minimalist application.

Architecture decisions
React frontend with Recharts and a responsive Swiss-style analytics workspace.
FastAPI backend with generated demo analytics, CSV upload validation, export endpoints and protected environment configuration.
MongoDB starter connection is preserved for future persistence; the current MVP is intentionally lightweight and serves the analytics contract from generated demo data.
Primary metric is on-time delivery rate; delivery success and revenue per shipment are supporting KPIs.
User personas
Internship analyst: explores evidence, tests hypotheses and exports management-ready outputs.
Hub or fleet manager: scans the driver tree, sees the affected hubs and owns measurable corrective actions.
Operations leader: uses the early-warning view to act before on-time performance crosses its floor.
Core requirements (static)
12-hub fictional logistics network with a falling on-time metric.
Five documented hypotheses with supported/rejected outcomes and test methods.
Driver tree explaining at least 80% of the decline.
Hub, trend, driver and early-warning breakdowns.
Generated demo dataset plus CSV upload entry point.
Downloadable memo, driver tree CSV and hypothesis log CSV.
Responsive minimalist UI with accessible test IDs.
Implemented
2026-11-07
Built the Overview workspace with KPI cards, weekly trend chart, hub performance table, driver preview and owned actions.
Added Driver tree, Hypothesis log and Early warning views with evidence, causal reasoning and operational targets.
Added FastAPI analytics, CSV upload validation and three export endpoints.
Added mobile responsive behavior and verified the live dashboard plus API flows with the testing agent.
Added a source archive at /app/logistics-data-analysis-source.zip.
Prioritized backlog
P0: Replace generated aggregates with a real cleaning/join pipeline for shipment, route, vehicle and scan files.
P1: Add a notebook with executable t-test, chi-square and regression calculations.
P1: Persist uploaded datasets and analysis runs in MongoDB.
P2: Add user-defined metric thresholds and scheduled weekly alert snapshots.
Remaining P0/P1/P2 tasks
P0: Real dataset ingestion and time-zone/event-order normalization.
P1: Statistical notebook and downloadable two-page PDF memo.
P1: Historical analysis run storage and comparison selector.
P2: Role-specific action queues and richer route/service segmentation.