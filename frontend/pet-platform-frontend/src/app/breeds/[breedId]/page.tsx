import { BreedDetail } from "@/features/breeds/breed-detail";

export default async function BreedDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ breedId: string }>;
  searchParams: Promise<{ petId?: string }>;
}) {
  const { breedId } = await params;
  const { petId } = await searchParams;
  return <BreedDetail breedId={breedId} petId={petId} />;
}
