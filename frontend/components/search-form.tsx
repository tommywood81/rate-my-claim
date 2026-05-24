type SearchFormProps = {
  defaultQuery?: string;
  action?: string;
  className?: string;
  large?: boolean;
};

export function SearchForm({
  defaultQuery = "",
  action = "/search",
  className = "",
  large = false,
}: SearchFormProps) {
  return (
    <form
      action={action}
      method="get"
      role="search"
      className={`flex flex-col gap-3 sm:flex-row sm:items-stretch ${className}`}
    >
      <label htmlFor="search-q" className="sr-only">
        Search claims
      </label>
      <input
        id="search-q"
        name="q"
        type="search"
        defaultValue={defaultQuery}
        placeholder="Search claims — try meaning or keywords…"
        className={`owid-input flex-1 ${large ? "min-h-[3rem] text-lg" : ""}`}
        autoComplete="off"
      />
      <button type="submit" className="owid-btn-primary shrink-0 sm:min-w-[7rem]">
        Search
      </button>
    </form>
  );
}
