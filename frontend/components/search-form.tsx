type SearchFormProps = {
  defaultQuery?: string;
  action?: string;
  className?: string;
};

export function SearchForm({
  defaultQuery = "",
  action = "/search",
  className = "",
}: SearchFormProps) {
  return (
    <form
      action={action}
      method="get"
      role="search"
      className={`flex flex-col gap-2 sm:flex-row ${className}`}
    >
      <label htmlFor="search-q" className="sr-only">
        Search claims
      </label>
      <input
        id="search-q"
        name="q"
        type="search"
        defaultValue={defaultQuery}
        placeholder="Search claims by meaning or keywords…"
        className="min-h-[44px] flex-1 rounded border border-[var(--border)] bg-white px-3 py-2 text-[var(--fg)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        autoComplete="off"
      />
      <button
        type="submit"
        className="min-h-[44px] rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
      >
        Search
      </button>
    </form>
  );
}
