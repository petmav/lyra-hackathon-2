import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class names with later classes winning over earlier ones.
 * Standard `cn` utility used by every component in this app.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
