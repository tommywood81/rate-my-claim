/** Staff-facing copy for on-demand claim AI analysis. */

export function formatLastAiRun(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString();
}

export function generateAiBlockMessage(reason: string | null | undefined): string | null {
  if (reason === "no_evidence") {
    return "On-demand analysis is disabled until evidence is on record.";
  }
  if (reason === "stub_provider") {
    return "On-demand analysis is disabled for stub/test AI rows — it would not reflect a live provider run.";
  }
  return null;
}
