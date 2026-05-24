"use client";

import { ClaimAiAnalysisPanel } from "@/app/claims/[slug]/claim-ai-panel";
import { generateAiBlockMessage } from "@/lib/claim-ai-moderation";
import { useSiteUser } from "@/lib/use-site-user";

type Props = {
  slug: string;
  lastAiRunAt?: string | null;
  generateAvailable?: boolean;
  blockReason?: string | null;
};

/** Staff-only maintenance control; hidden from public claim pages. */
export function ClaimStaffAiTools({
  slug,
  lastAiRunAt,
  generateAvailable,
  blockReason,
}: Props) {
  const { isStaff } = useSiteUser();
  if (!isStaff) {
    return null;
  }

  const blockMessage = generateAiBlockMessage(blockReason);

  return (
    <div className="mt-3 space-y-2 border-t border-dashed border-[var(--border)] pt-3">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Staff tools</p>
      {generateAvailable ? (
        <ClaimAiAnalysisPanel slug={slug} lastAiRunAt={lastAiRunAt} />
      ) : (
        blockMessage && <p className="text-xs text-[var(--muted)]">{blockMessage}</p>
      )}
    </div>
  );
}
