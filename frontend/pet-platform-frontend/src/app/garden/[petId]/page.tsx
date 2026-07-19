import { GardenView } from "@/features/garden/garden-view";

export default async function GardenPage({
  params,
  searchParams,
}: {
  params: Promise<{ petId: string }>;
  searchParams: Promise<{ reward?: string }>;
}) {
  const { petId } = await params;
  const { reward } = await searchParams;
  return <GardenView highlightedRewardId={reward} petId={petId} />;
}
