import React from 'react'

const Svg = ({ children, size = 24, ...props }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>
)

export const MapPin = (p) => <Svg {...p}><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></Svg>
export const Search = (p) => <Svg {...p}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></Svg>
export const Settings2 = (p) => <Svg {...p}><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></Svg>
export const ChevronDown = (p) => <Svg {...p}><path d="m6 9 6 6 6-6"/></Svg>
export const CircleDollarSign = (p) => <Svg {...p}><circle cx="12" cy="12" r="9"/><path d="M16 8.5c-.8-.8-2-1.2-4-1.2-2.2 0-3.5 1-3.5 2.5 0 4 7 1.8 7 5.3 0 1.5-1.3 2.6-3.7 2.6-1.7 0-3.1-.5-4-1.4M12 5v14"/></Svg>
export const Sparkles = (p) => <Svg {...p}><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3ZM5 15l.8 2.2L8 18l-2.2.8L5 21l-.8-2.2L2 18l2.2-.8L5 15Zm13-2 1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2Z"/></Svg>
export const Info = (p) => <Svg {...p}><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></Svg>
export const UsersRound = (p) => <Svg {...p}><path d="M16 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM17 11a4 4 0 0 0 0-8M22 20v-1.5a4 4 0 0 0-3-3.9"/></Svg>
export const Map = (p) => <Svg {...p}><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/></Svg>
export const Clock3 = (p) => <Svg {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l-3 2"/></Svg>
export const ArrowUpRight = (p) => <Svg {...p}><path d="M7 17 17 7M7 7h10v10"/></Svg>
export const AlertTriangle = (p) => <Svg {...p}><path d="M10.3 3.6 2.4 18a2 2 0 0 0 1.8 3h15.6a2 2 0 0 0 1.8-3L13.7 3.6a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></Svg>
export const X = (p) => <Svg {...p}><path d="m18 6-12 12M6 6l12 12"/></Svg>
export const Download = (p) => <Svg {...p}><path d="M12 3v12m0 0 5-5m-5 5-5-5M5 21h14"/></Svg>
export const Phone = (p) => <Svg {...p}><path d="M22 16.9v3a2 2 0 0 1-2.2 2 20 20 0 0 1-8.7-3.1 19.6 19.6 0 0 1-6-6A20 20 0 0 1 2 4.1 2 2 0 0 1 4 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.8a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.2-1.2a2 2 0 0 1 2.1-.5c.9.4 1.8.6 2.8.7a2 2 0 0 1 1.9 2.1Z"/></Svg>
export const LogOut = (p) => <Svg {...p}><path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-6"/></Svg>
export const Check = (p) => <Svg {...p}><path d="m20 6-11 11-5-5"/></Svg>
export const Building2 = (p) => <Svg {...p}><path d="M6 22V4h12v18M2 22h20M9 8h2M13 8h2M9 12h2M13 12h2M9 16h2M13 16h2"/></Svg>
export const Globe2 = (p) => <Svg {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></Svg>
export const ExternalLink = (p) => <Svg {...p}><path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></Svg>
export const Target = (p) => <Svg {...p}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></Svg>
export const LoaderCircle = (p) => <Svg {...p}><path d="M21 12a9 9 0 1 1-6.2-8.6"/></Svg>
