import { fireEvent, render, screen } from "@testing-library/react";
import { ApiError } from "@/lib/api";
import { IntervalPlot } from "./charts";
import { Badge, ErrorState, HealthBadge, Markdown, Table, Tabs } from "./ui";

describe("HealthBadge", () => {
  it("never relies on colour alone: renders an icon and a text label", () => {
    render(<HealthBadge health="red" />);
    expect(screen.getByText("Off track")).toBeInTheDocument();
    expect(screen.getByText("■")).toBeInTheDocument();
  });
  it("handles unknown health", () => {
    render(<HealthBadge health={null} />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("explains permission errors without exposing data", () => {
    render(<ErrorState error={new ApiError(403, "Performance-assessment features are disabled")} />);
    expect(screen.getByText(/Not available for your role or organisation/)).toBeInTheDocument();
    expect(screen.getByText(/disabled/)).toBeInTheDocument();
  });
  it("renders nothing without an error", () => {
    const { container } = render(<ErrorState error={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Markdown", () => {
  it("renders coordinator reports: headings, lists, bold and tables", () => {
    render(<Markdown text={"# Weekly status\n*Health: **RED***\n## Risks\n- Vendor slip\n| A | B |\n|---|---|\n| 1 | 2 |"} />);
    expect(screen.getByRole("heading", { level: 1, name: "Weekly status" })).toBeInTheDocument();
    expect(screen.getByText("Vendor slip").tagName).toBe("LI");
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("RED").tagName).toBe("STRONG");
  });
});

describe("Table and Tabs", () => {
  it("shows an empty state", () => {
    render(<Table head={["x"]} rows={[]} empty="Nothing here." />);
    expect(screen.getByText("Nothing here.")).toBeInTheDocument();
  });
  it("switches tabs", () => {
    const onChange = vi.fn();
    render(<Tabs value="a" onChange={onChange} tabs={[{ id: "a", label: "A" }, { id: "b", label: "B" }]} />);
    fireEvent.click(screen.getByRole("tab", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith("b");
    expect(screen.getByRole("tab", { name: "A" })).toHaveAttribute("aria-selected", "true");
  });
  it("renders badges", () => {
    render(<Badge tone="good">ok</Badge>);
    expect(screen.getByText("ok")).toBeInTheDocument();
  });
});

describe("IntervalPlot", () => {
  const items = [
    { label: "Employee A", estimate: 2.7, low: -2.8, high: 8.1 },
    { label: "Employee B", estimate: 3.0, low: -4.4, high: 10.3 },
  ];
  it("draws one interval per item with an accessible label", () => {
    render(<IntervalPlot items={items} />);
    expect(screen.getByRole("img", { name: /95% intervals/ })).toBeInTheDocument();
    expect(screen.getByText("Employee A")).toBeInTheDocument();
  });
  it("offers a table view of the same data", () => {
    render(<IntervalPlot items={items} />);
    fireEvent.click(screen.getByText("Show table"));
    expect(screen.getByText("95% high")).toBeInTheDocument();
    expect(screen.getByText("10.3")).toBeInTheDocument();
  });
});
