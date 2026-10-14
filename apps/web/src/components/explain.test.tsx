import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { Headlines, HowAssessed, ResultView } from "./explain";

describe("ResultView", () => {
  it("renders lists of records as a table and nested values readably", () => {
    render(<ResultView value={{ models: [{ model: "ridge", mae: 9.2214 }], note: "ok", n: 3 }} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("ridge")).toBeInTheDocument();
    expect(screen.getByText("9.221")).toBeInTheDocument();
    expect(screen.getByText("Models")).toBeInTheDocument();
  });
  it("shows a placeholder for missing values", () => {
    render(<ResultView value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("Headlines", () => {
  it("surfaces plain-language sentences first", () => {
    render(<Headlines result={{ plain_language: "Raw KPIs mostly reflect difficulty.", other: 1 }} />);
    expect(screen.getByText("Raw KPIs mostly reflect difficulty.")).toBeInTheDocument();
  });
});

describe("HowAssessed", () => {
  it("loads the metric definition on demand, including prohibited interpretations", async () => {
    const body = {
      label: "Adjusted", plain_language: "Compares outcomes with what conditions predict.", construct_label: "Contribution",
      evidence_status: "reasonable_hypothesis", unit: "pp", definition: "d", computation: "c", data_sources: ["jira"],
      assumptions: ["a"], limitations: ["l"], prohibited_interpretations: ["A ranking of people"],
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => body });
    vi.stubGlobal("fetch", fetchMock);
    render(<HowAssessed metric="adjusted_schedule_estimate" />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "How was this assessed?" }));
    await waitFor(() => expect(screen.getByText("Compares outcomes with what conditions predict.")).toBeInTheDocument());
    expect(screen.getByText("A ranking of people")).toBeInTheDocument();
    expect(screen.getByText("Reasonable hypothesis")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/measurement/metrics/adjusted_schedule_estimate");
    vi.unstubAllGlobals();
  });
});
