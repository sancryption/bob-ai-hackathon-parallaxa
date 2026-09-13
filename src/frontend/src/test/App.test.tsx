import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

// Stub the API so the test doesn't hit the network
vi.mock("../lib/apiClient", () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { status: "ok" } }),
  },
}));

describe("App", () => {
  it("renders SafetyReady heading", async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByText("SafetyReady")).toBeInTheDocument();
  });
});
