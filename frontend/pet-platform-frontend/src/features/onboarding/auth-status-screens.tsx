import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Banner, Card } from "@/components/primitives";

export function AuthLockedScreen() {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">تایید ورود</div>
          <h1 className="display">قفل موقت</h1>
        </div>
        <Card className="stack" role="alert">
          <Banner tone="error">
            تایید کد به دلیل تلاش‌های ناموفق پیاپی موقتاً قفل شده است.
          </Banner>
          <p className="caption">
            برای ادامه، کمی صبر کنید و سپس دوباره شماره موبایل خود را وارد
            کنید.
          </p>
          <Link className="button button--primary" href="/auth/mobile">
            بازگشت به ورود
          </Link>
        </Card>
      </div>
    </AppShell>
  );
}

export function AuthSessionExpiredScreen() {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">نشست</div>
          <h1 className="display">نشست شما پایان یافته است</h1>
        </div>
        <Card className="stack" role="alert">
          <Banner tone="warning">
            برای امنیت حساب، پس از مدتی عدم فعالیت باید دوباره وارد شوید.
          </Banner>
          <Link className="button button--primary" href="/auth/mobile">
            ورود دوباره
          </Link>
        </Card>
      </div>
    </AppShell>
  );
}
