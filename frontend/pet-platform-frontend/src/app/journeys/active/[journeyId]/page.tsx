import { JourneyActive } from "@/features/journeys/journey-active";

export default async function JourneyActivePage({
  params,
}: {
  params: Promise<{ journeyId: string }>;
}) {
  const { journeyId } = await params;
  return <JourneyActive journeyId={journeyId} />;
}
