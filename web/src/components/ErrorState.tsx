import { Card } from "./Card";

type Props = {
  title: string;
  body: string;
  onRetry?: () => void;
};

export function ErrorState({ title, body, onRetry }: Props) {
  return (
    <Card className="border-l-2 border-l-warn p-4">
      <div className="font-display text-sm font-bold text-primary">{title}</div>
      <p className="mt-1 text-sm text-muted">{body}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-base border border-hairline px-3 py-1.5 text-sm font-semibold text-primary hover:border-interactive"
        >
          Try again
        </button>
      ) : null}
    </Card>
  );
}
