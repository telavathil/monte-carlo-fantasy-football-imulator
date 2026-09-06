import { useEffect, useState } from "react";
import { onWarming } from "../api/auth";

export function useWarming(): boolean {
  const [warming, setWarming] = useState(false);
  useEffect(() => onWarming(setWarming), []);
  return warming;
}
