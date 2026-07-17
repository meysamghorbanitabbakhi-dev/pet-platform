"use client";

import { useState } from "react";
import { Button } from "@/components/primitives";
import { addCartItem } from "@/lib/cart";

export function AddToCartButton({
  disabled,
  offerId,
}: {
  disabled?: boolean;
  offerId: string;
}) {
  const [added, setAdded] = useState(false);
  return (
    <Button
      variant="selection"
      disabled={disabled}
      onClick={() => {
        addCartItem(offerId);
        setAdded(true);
      }}
    >
      {added ? "به سبد افزوده شد" : "افزودن به سبد"}
    </Button>
  );
}
