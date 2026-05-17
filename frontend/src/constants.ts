import type { ReadingStatus } from "./types";

export const STATUS_OPTIONS: ReadingStatus[] = ["unread", "reading", "completed", "owned", "wishlist"];

export const STATUS_TABS: Array<{ key: string; label: string }> = [
  { key: "all",       label: "All" },
  { key: "reading",   label: "Reading" },
  { key: "unread",    label: "Unread" },
  { key: "completed", label: "Completed" },
  { key: "owned",     label: "Owned" },
  { key: "wishlist",  label: "Wishlist" },
];

export const capitalize = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1);
