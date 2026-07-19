import { PetAssets } from "@/features/pets/pet-assets";

export default async function PetAssetsPage({
  params,
}: {
  params: Promise<{ petId: string }>;
}) {
  const { petId } = await params;
  return <PetAssets petId={petId} />;
}
