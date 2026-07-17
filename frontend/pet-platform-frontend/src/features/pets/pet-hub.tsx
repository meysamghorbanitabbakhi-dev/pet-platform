"use client";

import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/primitives";

export function PetHub({ petId }: { petId: string }) {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پت</div>
          <h1 className="display">پروفایل سلامت</h1>
        </div>

        <Link className="card stack" href={`/pets/${petId}/measurements`}>
          <span className="title">اندازه‌گیری‌ها</span>
          <span className="caption">ثبت وزن و مشاهده روند آن</span>
        </Link>

        <Link className="card stack" href={`/pets/${petId}/assets`}>
          <span className="title">تصاویر و اسناد</span>
          <span className="caption">
            آپلود خصوصی عکس یا مدرک پزشکی و بررسی وضعیت بدنی
          </span>
        </Link>

        <Link className="card stack" href={`/pets/${petId}/care`}>
          <span className="title">نژاد و راهنمای مراقبتی</span>
          <span className="caption">
            اطلاعات تاییدشده مرتبط با نژاد و راهنماهای مراقبتی
          </span>
        </Link>

        <Card className="stack">
          <p className="caption">
            محتوای این بخش اطلاعاتی است و جایگزین نظر دامپزشک نیست.
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
