import type { AIAnalysisItem } from "@/lib/types";

type AiAnalysisListProps = {
  items: AIAnalysisItem[];
};

export function AiAnalysisList({ items }: AiAnalysisListProps) {
  return (
    <ul className="space-y-4 text-sm" aria-label="AI-assisted analyses">
      {items.map((a) => (
        <li
          key={a.id}
          className="rounded border border-dashed border-[var(--border)] bg-white/80 p-3 border-l-4 border-l-[var(--accent)]"
        >
          <p className="text-xs text-[var(--muted)]">
            <span className="font-medium text-[var(--fg)]">{a.analysis_type}</span>
            {" · "}
            {a.provider} / {a.model_name}
            {" · "}
            <time dateTime={a.created_at}>{new Date(a.created_at).toLocaleString()}</time>
          </p>
          <p className="mt-2 whitespace-pre-wrap leading-relaxed">{a.generated_text}</p>
        </li>
      ))}
      {items.length === 0 && (
        <li className="text-[var(--muted)]">No AI analyses stored for this claim.</li>
      )}
    </ul>
  );
}
