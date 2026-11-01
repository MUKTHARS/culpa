export const ROUTES = {
  home: "/",
  login: "/login",
  agent: "/agent",
  checkoutReturn: "/checkout/return",
  merchant: "/merchant",
  cases: "/cases",
  caseDetail: (id: string) => `/cases/${id}`,
  orders: "/orders",
  benchmark: "/benchmark",
  jobs: "/jobs",
} as const;

export const ANALYST_NAV = [
  { href: ROUTES.cases, label: "Cases" },
  { href: ROUTES.orders, label: "Orders" },
  { href: ROUTES.benchmark, label: "Benchmark" },
  { href: ROUTES.jobs, label: "Jobs" },
] as const;
