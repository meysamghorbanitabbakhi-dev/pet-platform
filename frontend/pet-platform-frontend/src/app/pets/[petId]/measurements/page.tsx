import { PetMeasurements } from "@/features/pets/pet-measurements";

export default async function PetMeasurementsPage({
  params,
}: {
  params: Promise<{ petId: string }>;
}) {
  const { petId } = await params;
  return <PetMeasurements petId={petId} />;
}
