export const STATUS_OPTIONS = ["unread", "reading", "completed", "owned", "wishlist"];

export const STATUS_TABS = [
  { key: "all",       label: "All" },
  { key: "reading",   label: "Reading" },
  { key: "unread",    label: "Unread" },
  { key: "completed", label: "Completed" },
  { key: "owned",     label: "Owned" },
  { key: "wishlist",  label: "Wishlist" },
];

export const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);
