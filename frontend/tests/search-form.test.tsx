import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { SearchForm } from "@/components/search-form";

describe("SearchForm", () => {
  it("renders search input and submit button", () => {
    render(<SearchForm defaultQuery="vitamin" />);
    expect(screen.getByRole("search")).toBeInTheDocument();
    expect(screen.getByLabelText(/search claims/i)).toHaveValue("vitamin");
    expect(screen.getByRole("button", { name: /search/i })).toBeInTheDocument();
  });

  it("has no critical accessibility violations", async () => {
    const { container } = render(<SearchForm />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
