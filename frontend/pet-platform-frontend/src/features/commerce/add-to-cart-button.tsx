"use client";

import { useState } from "react";
import { Button, QuantityStepper } from "@/components/primitives";
import { addCartItem } from "@/lib/cart";

export function AddToCartButton({
  disabled,
  offerId,
}: {
  disabled?: boolean;
  offerId: string;
}) {
  const [added, setAdded] = useState(false);
  const [quantity, setQuantity] = useState(1);

  if (disabled) {
    return (
      <Button variant="selection" disabled>
        افزودن به سبد
      </Button>
    );
  }

  return (
    <div className="cluster">
      <QuantityStepper
        label="تعداد افزودن به سبد"
        max={100}
        min={1}
        onChange={setQuantity}
        value={quantity}
      />
      <Button
        variant="selection"
        onClick={() => {
          addCartItem(offerId, quantity);
          setAdded(true);
        }}
      >
        {added ? "به سبد افزوده شد" : "افزودن به سبد"}
      </Button>
    </div>
  );
}
