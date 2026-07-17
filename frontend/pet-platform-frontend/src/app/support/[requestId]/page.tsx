import { ConciergeRequestDetail } from "@/features/support/concierge-request-detail";

export default async function SupportRequestPage({
  params,
}: {
  params: Promise<{ requestId: string }>;
}) {
  const { requestId } = await params;
  return <ConciergeRequestDetail requestId={requestId} />;
}
