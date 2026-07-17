import { PetCare } from "@/features/pets/pet-care";

export default async function PetCarePage({
  params,
}: {
  params: Promise<{ petId: string }>;
}) {
  const { petId } = await params;
  return <PetCare petId={petId} />;
}
