type Props = {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

export function SearchInput({ value, onChange, placeholder = "Search players…" }: Props) {
  return (
    <input
      type="text"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="w-full rounded-base border border-hairline bg-well px-3 py-2 text-sm text-primary placeholder:text-muted focus:border-accent focus:outline-none"
    />
  );
}
