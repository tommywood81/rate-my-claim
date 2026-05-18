import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ClaimTimeline } from "@/components/claim-timeline";
import type { TimelineEvent } from "@/lib/types";

const sample: TimelineEvent[] = [
  {
    id: "1",
    event_type: "evidence",
    timestamp: "2026-05-17T12:00:00Z",
    title: "Evidence added: Study A",
    description: "Summary text",
    payload: {},
  },
  {
    id: "2",
    event_type: "contradiction_emergence",
    timestamp: "2026-05-18T12:00:00Z",
    title: "Contradiction linked",
    description: null,
    payload: { other_slug: "related-claim-slug" },
  },
];

describe("ClaimTimeline", () => {
  it("renders events in order", () => {
    render(<ClaimTimeline events={sample} />);
    expect(screen.getByText("Evidence added: Study A")).toBeInTheDocument();
    expect(screen.getByText("Contradiction linked")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view related claim/i })).toHaveAttribute(
      "href",
      "/claims/related-claim-slug",
    );
  });

  it("shows empty state", () => {
    render(<ClaimTimeline events={[]} />);
    expect(screen.getByText(/no timeline events/i)).toBeInTheDocument();
  });
});
