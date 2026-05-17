import React from "react";

const Logo = ({ size = 32 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="32" height="32" rx="7" fill="#0f172a"/>
    <path
      d="M16 8C14 8 10 9 8 11L8 24C10 22 14 21.5 16 21.5C18 21.5 22 22 24 24L24 11C22 9 18 8 16 8Z"
      stroke="#38bdf8" strokeWidth="1.6" strokeLinejoin="round"
    />
    <line x1="16" y1="8" x2="16" y2="21.5" stroke="#38bdf8" strokeWidth="1.6"/>
    <path d="M11 13C12 12.5 14 12.3 16 12.3" stroke="#7dd3fc" strokeWidth="1" opacity="0.6"/>
    <path d="M11 15.5C12 15 14 14.8 16 14.8" stroke="#7dd3fc" strokeWidth="1" opacity="0.6"/>
    <path d="M21 13C20 12.5 18 12.3 16 12.3" stroke="#7dd3fc" strokeWidth="1" opacity="0.6"/>
    <path d="M21 15.5C20 15 18 14.8 16 14.8" stroke="#7dd3fc" strokeWidth="1" opacity="0.6"/>
  </svg>
);

export default Logo;
