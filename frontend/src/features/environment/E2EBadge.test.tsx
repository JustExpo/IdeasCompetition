import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { observeMode, resetBuildObservation } from "../../api";
import { E2EBadge } from "./E2EBadge";

describe("E2EBadge", () => {
  afterEach(() => {
    resetBuildObservation();
  });

  it("скрыта в обычном режиме", () => {
    render(<E2EBadge />);
    expect(screen.queryByText("E2E MODE")).toBeNull();
  });

  it("появляется, когда сервер сообщил режим e2e", () => {
    render(<E2EBadge />);
    act(() => {
      observeMode("e2e");
    });
    expect(screen.getByText("E2E MODE")).toBeTruthy();
  });

  it("не реагирует на другие режимы", () => {
    render(<E2EBadge />);
    act(() => {
      observeMode("dev");
    });
    expect(screen.queryByText("E2E MODE")).toBeNull();
  });
});
