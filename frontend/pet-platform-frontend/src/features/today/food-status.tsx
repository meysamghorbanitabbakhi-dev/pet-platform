import { Banner, Card } from "@/components/primitives";
import type { PolicyResponse, TodayFood, TodayResponse } from "@/lib/api-types";
import { formatPersianNumber } from "@/lib/format";
import { enabled } from "@/lib/policy";

export function foodStatusText(
  food: TodayFood,
  policy: PolicyResponse,
): string {
  switch (food.state) {
    case "incoming":
      return `سفارش پرداخت‌شده در مسیر تأمین و تحویل است: ${food.label}`;
    case "unopened":
      return `بسته تحویل شده و هنوز باز شدن آن تأیید نشده است: ${food.label}`;
    case "unknown_estimate":
      return `بسته باز شده، اما سهم مصرف هنوز برای تخمین روز کافی نیست: ${food.label}`;
    case "estimated": {
      if (!enabled(policy, "semantic_level_estimation_enabled"))
        return `وضعیت غذا ثبت شده است: ${food.label}`;
      const high = food.remaining_high_days
        ? ` تا ${formatPersianNumber(food.remaining_high_days)}`
        : "";
      return `${formatPersianNumber(food.remaining_low_days)}${high} روز برآورد فعلی برای ${food.label}`;
    }
    case "unavailable":
      return "وضعیت غذا از سمت سرویس در دسترس نیست.";
    case "none":
      return "برای این پت غذای فعالی ثبت نشده است.";
  }
}

export function FoodStatusCard({
  today,
  policy,
}: {
  today: TodayResponse;
  policy: PolicyResponse;
}) {
  const { food } = today;
  const hasKnownProgress =
    food.state === "estimated" &&
    enabled(policy, "semantic_level_estimation_enabled");
  return (
    <Card className="stack">
      <div className="split">
        <div>
          <div className="eyebrow">وضعیت اصلی امروز</div>
          <h2 className="title">غذای {today.pet.name}</h2>
        </div>
        <span className="chip chip--active">
          {food.state === "estimated" ? "تخمین فعال" : "وضعیت فعلی"}
        </span>
      </div>
      <div
        className={hasKnownProgress ? "meter" : "meter meter--unknown"}
        role={hasKnownProgress ? "progressbar" : "img"}
        aria-label={
          hasKnownProgress
            ? "برآورد غذا با اطمینان متوسط"
            : "تخمین روز غذا هنوز شروع نشده است"
        }
        aria-valuemin={hasKnownProgress ? 0 : undefined}
        aria-valuemax={hasKnownProgress ? 100 : undefined}
        aria-valuenow={hasKnownProgress ? 64 : undefined}
      >
        {hasKnownProgress ? (
          <div className="meter__fill" style={{ inlineSize: "64%" }} />
        ) : null}
      </div>
      <p>{foodStatusText(food, policy)}</p>
      {food.state === "incoming" ? (
        <Banner tone="info">
          تأمین فقط پس از پرداخت کامل شروع می‌شود. زمان تعهد تحویل همین سفارش
          ۳۶۶ ساعت است.
        </Banner>
      ) : null}
      {food.state === "unopened" ? (
        <Banner tone="warning">
          تا وقتی باز شدن بسته را تأیید نکنید، عدد روز باقی‌مانده نمایش داده
          نمی‌شود.
        </Banner>
      ) : null}
    </Card>
  );
}

export function NextEventCard({ today }: { today: TodayResponse }) {
  const label =
    today.primary_attention?.type === "delivery_delayed"
      ? "تحویل با تأخیر ثبت شده است"
      : today.primary_attention?.type === "delivery_overdue"
        ? "تحویل از زمان تعهد گذشته است"
        : today.primary_attention?.type === "sourcing_failed"
          ? "تأمین سفارش ناموفق شده است"
          : today.next_action === "confirm_opening"
            ? "تأیید باز شدن بسته"
            : today.next_action === "improve_food_estimate"
              ? "بهبود تخمین مصرف"
              : "رویداد فوری ثبت نشده است";
  return (
    <Card className="stack">
      <div className="eyebrow">رویداد بعدی</div>
      <h2 className="title">{label}</h2>
      <p className="caption">
        این بخش فقط وضعیت فعلی را نشان می‌دهد و کار روزانه اجباری ایجاد نمی‌کند.
      </p>
    </Card>
  );
}
