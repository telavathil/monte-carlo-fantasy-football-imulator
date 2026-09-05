import { Card } from "./Card";

// No node ID, HTTP status, latency figure, or time estimate here — the Stitch mock's
// `NODE_AWS_EUC1 #084`, `HTTP 204 Waiting`, and `Est. 4-8s` are all fabricated (the app
// deploys on Fly, not AWS; there's no such status flow; the real cold boot is 15-25s).
export function WarmingPanel() {
  return (
    <Card className="mx-auto flex max-w-sm flex-col items-center gap-3 p-6 text-center">
      <h2 className="font-display text-base font-semibold text-primary">
        Waking the server up…
      </h2>
      <p className="text-sm text-muted">
        The API sleeps when idle to stay on the free tier. This only happens on the first
        load.
      </p>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-well">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />
      </div>
    </Card>
  );
}
