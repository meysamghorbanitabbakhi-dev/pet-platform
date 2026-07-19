export function checkInIdempotencyKey(
  journeyId: string,
  checkInKey: string,
  answerKey: string,
): string {
  return `checkin:${journeyId}:${checkInKey}:${answerKey}`.slice(0, 255);
}
