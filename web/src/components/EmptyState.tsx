import { Link } from "react-router-dom";

type Props = {
  title: string;
  body: string;
  actionLabel?: string;
  actionTo?: string;
};

export function EmptyState({ title, body, actionLabel, actionTo }: Props) {
  return (
    <div className="flex flex-col items-center gap-2 py-16 text-center">
      <h2 className="font-display text-lg font-semibold text-primary">{title}</h2>
      <p className="max-w-sm text-sm text-muted">{body}</p>
      {actionLabel && actionTo ? (
        <Link
          to={actionTo}
          className="mt-4 rounded-base bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:bg-accent/90"
        >
          {actionLabel}
        </Link>
      ) : null}
    </div>
  );
}
