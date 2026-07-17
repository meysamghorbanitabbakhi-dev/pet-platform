import { InventoryOpening } from "@/features/inventory/inventory-opening";

export default async function InventoryUnitPage({
  params,
}: {
  params: Promise<{ unitId: string }>;
}) {
  const { unitId } = await params;
  return <InventoryOpening unitId={unitId} />;
}
