import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InfoTooltip } from "./InfoTooltip";

describe("InfoTooltip", () => {
  it("renders a trigger labeled for how the value is calculated", () => {
    render(<InfoTooltip text="Some explanation.">?</InfoTooltip>);

    expect(
      screen.getByRole("button", { name: "How is this calculated?" })
    ).toBeInTheDocument();
  });

  it("renders the trigger's children as its visible content", () => {
    render(<InfoTooltip text="Some explanation.">?</InfoTooltip>);

    expect(
      screen.getByRole("button", { name: "How is this calculated?" })
    ).toHaveTextContent("?");
  });

  it("associates the disclaimer text with the trigger via aria-describedby", () => {
    render(<InfoTooltip text="Some explanation.">?</InfoTooltip>);

    const trigger = screen.getByRole("button", {
      name: "How is this calculated?",
    });
    const describedById = trigger.getAttribute("aria-describedby");

    expect(describedById).toBeTruthy();
    expect(
      document.getElementById(describedById as string)
    ).toHaveTextContent("Some explanation.");
  });
});
