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
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
  }, []);
  return (
    <div className="dialog-backdrop" role="presentation">
      <div
        className="dialog stack"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
      >
        <div className="split">
          <h2 className="title" id="dialog-title">
            {title}
          </h2>
          <IconButton ref={closeRef} label="بستن" onClick={onClose}>
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
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="sheet-backdrop" role="presentation">
      <div
        className="sheet stack"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sheet-title"
      >
        <h2 className="title" id="sheet-title">
          {title}
        </h2>
        {children}
      </div>
    </div>
  );
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
  return (
    <div className="pet-switcher" role="tablist" aria-label="انتخاب پت">
      {pets.map((pet) => (
        <button
          className="pet-tab"
          key={pet.id}
          role="tab"
          aria-selected={pet.id === activePetId}
          tabIndex={pet.id === activePetId ? 0 : -1}
          onClick={() => onSelect(pet.id)}
        >
          <span aria-hidden="true">●</span>
          {pet.name}
        </button>
      ))}
    </div>
  );
}

export function BottomNav() {
  const pathname = usePathname();
  const items = [
    { href: "/today", label: "امروز", icon: Home },
    { href: "/inventory/open", label: "انبار", icon: PackageOpen },
    { href: "/today#garden", label: "باغ", icon: Leaf },
    { href: "/shop", label: "فروشگاه", icon: ShoppingBag },
    { href: "/auth/mobile", label: "حساب", icon: UserRound },
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
