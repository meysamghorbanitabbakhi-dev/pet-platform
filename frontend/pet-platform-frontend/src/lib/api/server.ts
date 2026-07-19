import "server-only";

import {
  getOfferDetailBackend,
  getPoliciesBackend,
  listOffersBackend,
} from "./backend";

export async function listOffersServer() {
  return listOffersBackend();
}

export async function getPoliciesServer() {
  return getPoliciesBackend();
}

export async function getOfferDetailServer(offerId: string) {
  return getOfferDetailBackend(offerId);
}
