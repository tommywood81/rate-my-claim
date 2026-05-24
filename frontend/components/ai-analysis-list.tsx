import type { AIAnalysisItem } from "@/lib/types";

type AiAnalysisListProps = {
  items: AIAnalysisItem[];
};

export function AiAnalysisList({ items }: AiAnalysisListProps) {
  return (
    <ul className="space-y-4 text-sm" aria-label="AI-assisted analyses">
      {items.map((a) => (
        <li key={a.id} className="owid-card border-l-4 border-l-[var(--accent-warm)] p-4">
          <p className="text-xs text-[var(--muted)]">
            <span className="font-semibold text-[var(--accent-dark)]">{a.analysis_type}</span>
            {" · "}
            {a.provider} / {a.model_name}
            {" · "}
            <time dateTime={a.created_at}>{new Date(a.created_at).toLocaleString()}</time>
          </p>
          <p className="mt-2 whitespace-pre-wrap leading-relaxed text-[var(--fg)]">{a.generated_text}</p>
        </li>
      ))}
      {items.length === 0 && (
        <li className="text-[var(--muted)]">No AI write-up on this claim yet.</li>
      )}
    </ul>
  );
}
