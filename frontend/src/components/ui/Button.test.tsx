import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Button from "./Button";

describe("Button", () => {
  it("renders children normally", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("is not disabled and has no spinner by default", () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole("button");
    expect(btn).not.toBeDisabled();
    expect(btn).not.toHaveAttribute("aria-busy");
    expect(btn.querySelector(".button__spinner")).toBeNull();
  });

  it("when loading=true: sets aria-busy, disables, shows spinner", () => {
    render(<Button loading>Save</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(btn).toBeDisabled();
    expect(btn.querySelector(".button__spinner")).not.toBeNull();
  });

  it("when loading=true: hides icon and shows spinner instead", () => {
    const FakeIcon = () => <svg data-testid="icon" />;
    render(<Button loading icon={FakeIcon}>Save</Button>);
    const btn = screen.getByRole("button");
    expect(btn.querySelector("[data-testid='icon']")).toBeNull();
    expect(btn.querySelector(".button__spinner")).not.toBeNull();
  });

  it("when loading=false and icon provided: shows icon, no spinner", () => {
    const FakeIcon = () => <svg data-testid="icon" />;
    render(<Button icon={FakeIcon}>Save</Button>);
    const btn = screen.getByRole("button");
    expect(screen.getByTestId("icon")).toBeInTheDocument();
    expect(btn.querySelector(".button__spinner")).toBeNull();
  });

  it("disabled prop still disables without loading", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("when loading=true: caller aria-busy prop cannot override loading state", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<Button loading {...({ "aria-busy": "false" } as any)}>Save</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-busy", "true");
  });

  it("when loading=true: button is disabled even if disabled={false} is passed", () => {
    render(<Button loading disabled={false}>Save</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
