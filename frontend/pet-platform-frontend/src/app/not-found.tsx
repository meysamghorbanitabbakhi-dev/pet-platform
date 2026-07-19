import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/primitives";

export default function NotFound() {
  return (
    <AppShell>
      <EmptyState
        title="این صفحه پیدا نشد"
        body="نشانی وارد شده در دسترس نیست یا جابه‌جا شده است."
        action={
          <Link className="button button--primary" href="/today">
            بازگشت به امروز
          </Link>
        }
      />
    </AppShell>
  );
}
