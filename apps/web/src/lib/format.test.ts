import { CONCLUSION_TEXT, label, num, pct, signed } from "./format";

describe("format helpers", () => {
  it("formats missing values as an em dash rather than zero", () => {
    expect(pct(null)).toBe("—");
    expect(num(undefined)).toBe("—");
    expect(signed(Number.NaN)).toBe("—");
  });
  it("formats numbers", () => {
    expect(pct(0.456)).toBe("46%");
    expect(signed(2.345)).toBe("+2.3");
    expect(signed(-1)).toBe("-1.0");
    expect(label("above_context_expectation")).toBe("Above context expectation");
  });
  it("describes insufficient evidence as an abstention", () => {
    expect(CONCLUSION_TEXT.insufficient_evidence).toMatch(/no conclusion/);
  });
});
