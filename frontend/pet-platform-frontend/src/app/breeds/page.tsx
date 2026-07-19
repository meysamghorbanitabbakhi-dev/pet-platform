import { BreedSearch } from "@/features/breeds/breed-search";

export default async function BreedsPage({
  searchParams,
}: {
  searchParams: Promise<{ petId?: string }>;
}) {
  const { petId } = await searchParams;
  return <BreedSearch petId={petId} />;
}
