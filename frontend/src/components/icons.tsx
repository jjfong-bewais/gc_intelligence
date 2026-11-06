import { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };
const base = ({ size = 16, ...p }: P) => ({
  width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, ...p,
});

export const IconSearch = (p: P) => <svg {...base(p)}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>;
export const IconThumbUp = (p: P) => <svg {...base(p)}><path d="M7 10v11H4V10h3Zm0 0 4-7c1.7 0 2.5 1 2.2 2.6L12.6 9H19a2 2 0 0 1 2 2.3l-1.3 7.5A2.5 2.5 0 0 1 17.2 21H7" /></svg>;
export const IconThumbDown = (p: P) => <IconThumbUp {...p} style={{ transform: "rotate(180deg)", ...p.style }} />;
export const IconBookmark = ({ filled, ...p }: P & { filled?: boolean }) => <svg {...base(p)} fill={filled ? "currentColor" : "none"}><path d="M6 3h12v18l-6-4-6 4V3Z" /></svg>;
export const IconBell = (p: P) => <svg {...base(p)}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></svg>;
export const IconClock = (p: P) => <svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>;
export const IconExternal = (p: P) => <svg {...base(p)}><path d="M14 4h6v6" /><path d="M20 4 10 14" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>;
export const IconArrowLeft = (p: P) => <svg {...base(p)}><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></svg>;
export const IconLogout = (p: P) => <svg {...base(p)}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></svg>;
export const IconX = (p: P) => <svg {...base(p)}><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>;
export const IconUpload = (p: P) => <svg {...base(p)}><path d="M12 15V3" /><path d="m7 8 5-5 5 5" /><path d="M5 21h14" /></svg>;
