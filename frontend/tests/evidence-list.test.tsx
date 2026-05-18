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
    const link = screen.getByRole("link", { name: /cardiovascular study/i });
    expect(link).toHaveAttribute("href", "https://example.com/paper");
  });

  it("returns null when empty", () => {
    const { container } = render(<EvidenceList title="Empty" items={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
