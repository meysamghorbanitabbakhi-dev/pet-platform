import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  Button,
  Input,
  Money,
  MeterBand,
  OrderTimeline,
  OtpInput,
  PetSwitcher,
  QuantityStepper,
  StatusChip,
} from "./primitives";
import { meContextFixture } from "@/test/fixtures/gate-fixtures";

describe("accessible primitives", () => {
  it("labels inputs and keeps minimum interactive controls focusable", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Input id="name" label="نام" />
        <Button>ثبت</Button>
      </>,
    );

    await user.tab();
    expect(screen.getByLabelText("نام")).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "ثبت" })).toHaveFocus();
  });

  it("renders OTP as one labeled input with visual cells", () => {
    render(<OtpInput value="123" onChange={() => {}} />);
    expect(screen.getByLabelText("کد تایید")).toHaveValue("123");
  });

  it("uses tablist semantics for pet switching", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <PetSwitcher
        pets={meContextFixture.pets}
        activePetId={meContextFixture.pets[0].id}
        onSelect={onSelect}
      />,
    );
    expect(
      screen.getByRole("tablist", { name: "انتخاب پت" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /رکس/ }));
    expect(onSelect).toHaveBeenCalledWith(meContextFixture.pets[1].id);
  });

  it("renders money with a full-amount aria-label and تومان unit", () => {
    render(<Money irr={125000} />);
    expect(screen.getByLabelText("۱۲٬۵۰۰ تومان")).toBeInTheDocument();
  });

  it("shows a loading skeleton instead of a fabricated amount", () => {
    render(<Money irr={null} loading />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("labels a status chip by tone without relying on color alone", () => {
    render(<StatusChip tone="warning">در انتظار</StatusChip>);
    expect(screen.getByText("در انتظار")).toBeInTheDocument();
  });

  it("renders a meter band as a striped unknown image, never a fabricated score, when confidence is unknown", () => {
    render(<MeterBand confidence={null} />);
    const meter = screen.getByRole("img");
    expect(meter).not.toHaveAttribute("aria-valuenow");
  });

  it("renders a meter band aria-label from confidence word, not a raw score", () => {
    render(<MeterBand confidence="medium" />);
    expect(
      screen.getByRole("progressbar", { name: "اطمینان متوسط" }),
    ).toBeInTheDocument();
  });

  it("marks the current step in an order timeline", () => {
    render(
      <OrderTimeline
        steps={[
          { key: "a", label: "ثبت سفارش", tone: "positive" },
          { key: "b", label: "در حال تامین", tone: "info", current: true },
        ]}
      />,
    );
    expect(screen.getByText("در حال تامین").closest("li")).toHaveAttribute(
      "aria-current",
      "step",
    );
  });

  it("disables the quantity stepper at min/max bounds", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<QuantityStepper value={1} min={1} max={2} onChange={onChange} />);
    expect(screen.getByLabelText("کاهش تعداد")).toBeDisabled();
    await user.click(screen.getByLabelText("افزایش تعداد"));
    expect(onChange).toHaveBeenCalledWith(2);
  });
});
