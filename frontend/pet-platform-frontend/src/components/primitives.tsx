"use client";

import clsx from "clsx";
import {
  AlertCircle,
  Home,
  Leaf,
  PackageOpen,
  ShoppingBag,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from "react";
import { forwardRef, useEffect, useRef } from "react";
import type { ContextPetSummary } from "@/lib/api-types";
import { formatTomanFromIrr } from "@/lib/format";

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "selection" | "secondary" | "ghost";
    loading?: boolean;
  }
>(function Button(
  { variant = "primary", loading, className, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={clsx("button", `button--${variant}`, className)}
      aria-busy={loading || undefined}
      disabled={props.disabled || loading}
      {...props}
    >
      {loading ? "در حال انجام" : children}
    </button>
  );
});

export const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & {
    label: string;
    children: ReactNode;
  }
>(function IconButton({ label, children, ...props }, ref) {
  return (
    <Button
      ref={ref}
      variant="secondary"
      className="icon-button"
      aria-label={label}
      title={label}
      {...props}
    >
      {children}
    </Button>
  );
});

export function Input({
  label,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  return (
    <div className="field">
      <label htmlFor={props.id}>{label}</label>
      <input
        className="input"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${props.id}-error` : undefined}
        {...props}
      />
      {error ? (
        <div className="inline-error" id={`${props.id}-error`}>
          {error}
        </div>
      ) : null}
    </div>
  );
}

export function OtpInput({
  value,
  onChange,
  invalid,
}: {
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
}) {
  const cells = Array.from({ length: 6 }, (_, index) => value[index] ?? "");
  return (
    <div className="field">
      <label htmlFor="otp-code">کد تایید</label>
      <input
        id="otp-code"
        className="input"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={6}
        value={value}
        onChange={(event) =>
          onChange(event.target.value.replace(/\D/g, "").slice(0, 6))
        }
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? "otp-code-error" : undefined}
      />
      <div className="otp-row" aria-hidden="true">
        {cells.map((cell, index) => (
          <div
            className="otp-cell"
            aria-invalid={invalid || undefined}
            key={index}
          >
            {cell}
          </div>
        ))}
      </div>
      {invalid ? (
        <div className="inline-error" id="otp-code-error">
          کد وارد شده معتبر نیست
        </div>
      ) : null}
    </div>
  );
}

export function Card({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLElement> & { children: ReactNode }) {
  return (
    <section className={clsx("card", className)} {...props}>
      {children}
    </section>
  );
}

export function Banner({
  tone = "info",
  children,
}: {
  tone?: "info" | "warning" | "error";
  children: ReactNode;
}) {
  return (
    <div
      className={clsx("banner", `banner--${tone}`)}
      role={tone === "error" ? "alert" : "status"}
    >
      <AlertCircle size={18} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function Skeleton({
  label = "در حال بارگذاری",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={clsx("skeleton", className)}
      role="status"
      aria-label={label}
    />
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="stack" aria-live="polite">
      <div className="title">{title}</div>
      {body ? <p className="caption">{body}</p> : null}
      {action}
    </Card>
  );
}

export function ErrorState({
  title = "خطا در دریافت داده",
  body,
  action,
}: {
  title?: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="stack" role="alert">
      <div className="title">{title}</div>
      {body ? <p className="caption">{body}</p> : null}
      {action}
    </Card>
  );
}

export function Toast({ children }: { children: ReactNode }) {
  return <div className="toast banner banner--info">{children}</div>;
}

export function Dialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const dialogRef = useFocusTrap(onClose);
  return (
    <div className="dialog-backdrop" role="presentation">
      <div
        ref={dialogRef}
        className="dialog stack"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
      >
        <div className="split">
          <h2 className="title" id="dialog-title">
            {title}
          </h2>
          <IconButton label="بستن" onClick={onClose}>
            <X size={18} aria-hidden="true" />
          </IconButton>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Sheet({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const sheetRef = useFocusTrap(onClose);
  return (
    <div className="sheet-backdrop" role="presentation">
      <div
        ref={sheetRef}
        className="sheet stack"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sheet-title"
      >
        <div className="split">
          <h2 className="title" id="sheet-title">
            {title}
          </h2>
          <IconButton label="بستن" onClick={onClose}>
            <X size={18} aria-hidden="true" />
          </IconButton>
        </div>
        {children}
      </div>
    </div>
  );
}

function useFocusTrap(onClose: () => void) {
  const containerRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previous = document.activeElement;
    const container = containerRef.current;
    if (!container) return;
    const activeContainer = container;

    const focusableSelector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");

    const focusable = Array.from(
      container.querySelectorAll<HTMLElement>(focusableSelector),
    );
    if (!focusable.length) container.tabIndex = -1;
    (focusable[0] ?? container).focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const currentFocusable = Array.from(
        activeContainer.querySelectorAll<HTMLElement>(focusableSelector),
      );
      if (!currentFocusable.length) {
        event.preventDefault();
        activeContainer.focus();
        return;
      }

      const first = currentFocusable[0];
      const last = currentFocusable[currentFocusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previous instanceof HTMLElement) previous.focus();
    };
    // Intentionally run once per mount: re-running on every onClose identity
    // change (e.g. an inline arrow function re-created on parent re-render)
    // would re-steal focus to the first focusable element on every keystroke
    // inside the trap. onCloseRef always holds the latest callback.
  }, []);

  return containerRef;
}

export function PetSwitcher({
  pets,
  activePetId,
  onSelect,
}: {
  pets: ContextPetSummary[];
  activePetId: string;
  onSelect: (petId: string) => void;
}) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const activeIndex = Math.max(
    pets.findIndex((pet) => pet.id === activePetId),
    0,
  );

  const selectByIndex = (index: number) => {
    const pet = pets[index];
    if (!pet) return;
    onSelect(pet.id);
    requestAnimationFrame(() => tabRefs.current[index]?.focus());
  };

  return (
    <div className="pet-switcher" role="tablist" aria-label="انتخاب پت">
      {pets.map((pet, index) => (
        <button
          className="pet-tab"
          key={pet.id}
          ref={(element) => {
            tabRefs.current[index] = element;
          }}
          role="tab"
          aria-selected={pet.id === activePetId}
          tabIndex={pet.id === activePetId ? 0 : -1}
          onClick={() => onSelect(pet.id)}
          onKeyDown={(event) => {
            if (
              !["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)
            ) {
              return;
            }
            event.preventDefault();
            if (event.key === "Home") {
              selectByIndex(0);
              return;
            }
            if (event.key === "End") {
              selectByIndex(pets.length - 1);
              return;
            }
            const direction = event.key === "ArrowRight" ? -1 : 1;
            selectByIndex(
              (activeIndex + direction + pets.length) % pets.length,
            );
          }}
        >
          <span aria-hidden="true">●</span>
          {pet.name}
        </button>
      ))}
    </div>
  );
}

export function Money({
  irr,
  loading,
}: {
  irr: number | null | undefined;
  loading?: boolean;
}) {
  if (loading || irr === null || irr === undefined) {
    return <Skeleton className="money-skeleton" label="در حال محاسبه مبلغ" />;
  }
  const label = formatTomanFromIrr(irr);
  return (
    <span className="money" aria-label={`${label.replace(" تومان", "")} تومان`}>
      {label}
    </span>
  );
}

const statusChipTone: Record<
  "positive" | "info" | "warning" | "error" | "muted",
  string
> = {
  positive: "chip--positive",
  info: "chip--info",
  warning: "chip--warning",
  error: "chip--error",
  muted: "chip--muted",
};

export function StatusChip({
  tone = "muted",
  glyph,
  children,
}: {
  tone?: "positive" | "info" | "warning" | "error" | "muted";
  glyph?: ReactNode;
  children: ReactNode;
}) {
  return (
    <span className={clsx("chip", statusChipTone[tone])}>
      {glyph}
      {children}
    </span>
  );
}

const confidenceFill: Record<"low" | "medium" | "high", number> = {
  low: 33,
  medium: 66,
  high: 100,
};

const confidenceLabelFa: Record<"low" | "medium" | "high", string> = {
  low: "اطمینان کم",
  medium: "اطمینان متوسط",
  high: "اطمینان زیاد",
};

export function MeterBand({
  confidence,
  loading,
}: {
  confidence: "low" | "medium" | "high" | null;
  loading?: boolean;
}) {
  if (loading) return <Skeleton className="meter" label="در حال بارگذاری برآورد" />;
  const known = confidence !== null;
  return (
    <div
      className={clsx("meter", !known && "meter--unknown")}
      role={known ? "progressbar" : "img"}
      aria-label={known ? confidenceLabelFa[confidence] : "برآورد هنوز نامشخص است"}
      aria-valuemin={known ? 0 : undefined}
      aria-valuemax={known ? 100 : undefined}
      aria-valuenow={known ? confidenceFill[confidence] : undefined}
    >
      {known ? (
        <div
          className="meter__fill"
          style={{ inlineSize: `${confidenceFill[confidence]}%` }}
        />
      ) : null}
    </div>
  );
}

export type OrderTimelineStep = {
  key: string;
  label: string;
  timestamp?: string | null;
  tone?: "positive" | "info" | "warning" | "error" | "muted";
  current?: boolean;
};

export function OrderTimeline({ steps }: { steps: OrderTimelineStep[] }) {
  return (
    <ol className="order-timeline">
      {steps.map((step) => (
        <li
          key={step.key}
          className={clsx(
            "order-timeline__step",
            step.tone && `order-timeline__step--${step.tone}`,
          )}
          aria-current={step.current ? "step" : undefined}
        >
          <span className="order-timeline__marker" aria-hidden="true" />
          <div>
            <div className="order-timeline__label">{step.label}</div>
            {step.timestamp ? (
              <div className="caption">{step.timestamp}</div>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function QuantityStepper({
  value,
  min = 1,
  max = 100,
  onChange,
  label = "تعداد",
}: {
  value: number;
  min?: number;
  max?: number;
  onChange: (value: number) => void;
  label?: string;
}) {
  return (
    <div className="quantity-stepper" role="group" aria-label={label}>
      <IconButton
        label="کاهش تعداد"
        disabled={value <= min}
        onClick={() => onChange(Math.max(min, value - 1))}
      >
        −
      </IconButton>
      <span aria-live="polite" className="quantity-stepper__value">
        {formatPersianNumberInline(value)}
      </span>
      <IconButton
        label="افزایش تعداد"
        disabled={value >= max}
        onClick={() => onChange(Math.min(max, value + 1))}
      >
        +
      </IconButton>
    </div>
  );
}

function formatPersianNumberInline(value: number) {
  return new Intl.NumberFormat("fa-IR", { numberingSystem: "arabext" }).format(
    value,
  );
}

export function GardenObject({
  label,
  placed,
  onClick,
}: {
  label: string;
  placed: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={clsx("garden-object", placed && "garden-object--placed")}
      onClick={onClick}
      disabled={!onClick}
    >
      <span className="garden-object__mark" aria-hidden="true" />
      <span className="garden-object__label">{label}</span>
    </button>
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const items = [
    { href: "/today", label: "امروز", icon: Home },
    { href: "/inventory", label: "انبار", icon: PackageOpen },
    { href: "/today#garden", label: "باغ", icon: Leaf },
    { href: "/shop", label: "فروشگاه", icon: ShoppingBag },
    { href: "/account", label: "حساب", icon: UserRound },
  ];
  return (
    <nav className="bottom-nav" aria-label="ناوبری اصلی">
      <div className="bottom-nav__inner">
        {items.map((item) => {
          const Icon = item.icon;
          const current =
            pathname === item.href ||
            (item.href !== "/today" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={current ? "page" : undefined}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
