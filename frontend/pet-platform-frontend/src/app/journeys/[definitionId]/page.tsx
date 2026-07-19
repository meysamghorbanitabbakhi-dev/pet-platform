import { JourneyDefinitionDetail } from "@/features/journeys/journey-definition-detail";

export default async function JourneyDefinitionPage({
  params,
}: {
  params: Promise<{ definitionId: string }>;
}) {
  const { definitionId } = await params;
  return <JourneyDefinitionDetail definitionId={definitionId} />;
}
