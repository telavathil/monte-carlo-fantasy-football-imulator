import type { ReactNode } from "react";

type Props = {
  className?: string;
  children: ReactNode;
};

export function Card({ className, children }: Props) {
  return (
    <div
      className={`rounded-panel border border-hairline bg-card${
        className ? ` ${className}` : ""
      }`}
    >
      {children}
    </div>
  );
}
