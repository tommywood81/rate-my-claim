import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceList } from "@/components/evidence-list";

describe("EvidenceList", () => {
  it("renders evidence cards with links", () => {
    render(
      <EvidenceList
        title="Supporting"
        variant="prominent"
        items={[
          {
            id: "e1",
            title: "Cardiovascular study",
            url: "https://example.com/paper",
            publisher: "Example Press",
            stance: "supports",
            credibility_score: 0.72,
            summary: "Findings support moderate exercise.",
            retrieval_timestamp: "2026-05-17T10:00:00Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("Supporting (1)")).toBeInTheDocument();
    expect(screen.getByText("https://example.com/paper")).toHaveAttribute(
      "href",
      "https://example.com/paper",
    );
    expect(screen.getByRole("link", { name: /open source \(example\.com\)/i })).toHaveAttribute(
      "href",
      "https://example.com/paper",
    );
    expect(screen.getByText(/findings support moderate exercise/i)).toBeInTheDocument();
    expect(screen.getByText(/saved 17\/05\/2026/i)).toBeInTheDocument();
  });

  it("returns null when empty", () => {
    const { container } = render(<EvidenceList title="Empty" items={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
