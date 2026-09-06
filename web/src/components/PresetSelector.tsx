import type { Preset } from "../api/types";

type Props = {
  value: Preset;
  onChange: (value: Preset) => void;
};

const LABELS: Record<Preset, string> = {
  standard: "Standard",
  half_ppr: "Half PPR",
  full_ppr: "Full PPR",
};

export function PresetSelector({ value, onChange }: Props) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value as Preset)}
      className="rounded-base border border-hairline bg-elevated px-2 py-1.5 text-sm text-primary focus:border-accent focus:outline-none"
    >
      {(Object.keys(LABELS) as Preset[]).map((preset) => (
        <option key={preset} value={preset}>
          {LABELS[preset]}
        </option>
      ))}
    </select>
  );
}
