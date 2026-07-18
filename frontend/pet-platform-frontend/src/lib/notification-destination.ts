import type { NotificationDestinationResponse } from "@/lib/api-types";

// Explicit allowlist from a typed destination.kind to an internal route --
// never build a URL from event_key/payload guessing, and never pass through
// or render an arbitrary URL from the backend. Kinds not present here (or
// "none") intentionally have no destination.
const ROUTE_BY_KIND: Partial<
  Record<NotificationDestinationResponse["kind"], (id: string) => string>
> = {
  order: (id) => `/orders/${id}`,
  inventory_unit: (id) => `/inventory/${id}`,
  journey: (id) => `/journeys/active/${id}`,
  customer_request: (id) => `/support/${id}`,
  offer: (id) => `/shop/offer/${id}`,
};

export function notificationDestinationHref(
  destination: NotificationDestinationResponse,
): string | null {
  if (!destination.id) return null;
  const toHref = ROUTE_BY_KIND[destination.kind];
  return toHref ? toHref(destination.id) : null;
}
