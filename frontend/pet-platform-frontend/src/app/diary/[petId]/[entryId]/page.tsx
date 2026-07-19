import { DiaryEntryDetail } from "@/features/diary/diary-entry-detail";

export default async function DiaryEntryPage({
  params,
}: {
  params: Promise<{ petId: string; entryId: string }>;
}) {
  const { petId, entryId } = await params;
  return <DiaryEntryDetail entryId={entryId} petId={petId} />;
}
