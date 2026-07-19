import { PetHub } from "@/features/pets/pet-hub";

export default async function PetHubPage({
  params,
}: {
  params: Promise<{ petId: string }>;
}) {
  const { petId } = await params;
  return <PetHub petId={petId} />;
}
