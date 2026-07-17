import { redirect } from "next/navigation";
import { getMeContextBackend } from "@/lib/api/backend";
import { routeFromMeContext } from "@/lib/onboarding-routing";

export const dynamic = "force-dynamic";

export default async function OnboardingBootstrapPage() {
  let destination: ReturnType<typeof routeFromMeContext> = "/auth/mobile";
  try {
    const context = await getMeContextBackend();
    destination = routeFromMeContext(context);
  } catch {
    redirect("/auth/mobile");
  }
  redirect(destination);
}
