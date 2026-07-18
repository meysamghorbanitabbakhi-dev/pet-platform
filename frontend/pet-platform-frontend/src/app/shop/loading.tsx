import { AppShell } from "@/components/app-shell";
import { Card, Skeleton } from "@/components/primitives";

export default function ShopLoading() {
  return (
    <AppShell wide>
      <div className="stack">
        <div>
          <div className="eyebrow">فروشگاه</div>
          <h1 className="display">کشف محصول</h1>
        </div>
        <div className="grid grid--two">
          {[0, 1, 2, 3].map((index) => (
            <Card key={index} className="stack">
              <Skeleton />
              <Skeleton />
              <Skeleton />
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
