import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

const NAV = [
  { to: "/players", label: "Players" },
  { to: "/import", label: "Import" },
  { to: "/", label: "Settings" },
] as const;

type Props = {
  children: ReactNode;
  preset?: ReactNode;
};

export function AppShell({ children, preset }: Props) {
  const { pathname } = useLocation();
  return (
    <div className="min-h-full bg-canvas text-primary font-body">
      <header className="sticky top-0 z-10 flex items-center gap-6 border-b border-hairline bg-card px-6 py-3">
        <span className="font-display text-base font-bold tracking-tight">MC Sim</span>
        <nav className="flex items-center gap-1">
          {NAV.map((item) => {
            const active =
              item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={
                  active
                    ? "rounded-base bg-accent px-3 py-1.5 text-sm font-semibold text-canvas"
                    : "rounded-base px-3 py-1.5 text-sm text-muted hover:text-primary"
                }
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto">{preset}</div>
      </header>
      <main className="mx-auto max-w-[1440px] px-6 py-6">{children}</main>
    </div>
  );
}
