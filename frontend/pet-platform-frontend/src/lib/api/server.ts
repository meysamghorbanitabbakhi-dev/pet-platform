import "server-only";

import { getPoliciesBackend, listOffersBackend } from "./backend";

export async function listOffersServer() {
  return listOffersBackend();
}

export async function getPoliciesServer() {
  return getPoliciesBackend();
}
