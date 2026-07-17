import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button, Input, OtpInput, PetSwitcher } from "./primitives";
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
});
