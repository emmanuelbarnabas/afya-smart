// Monogram ya Afya Smart — kisanduku cha kijani + herufi 'A' + pulse.
// Sawa kabisa na backend/app/static/logo.svg (SVG moja kwa moja = pixel-perfect).
export default function Logo({ size = 48, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className={className}
      role="img"
      aria-label="Afya Smart"
    >
      <defs>
        <linearGradient
          id="afyaLogoGrad"
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="64"
          y2="64"
        >
          <stop offset="0" stopColor="#16a066" />
          <stop offset="1" stopColor="#085c39" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="20" fill="url(#afyaLogoGrad)" />
      <path fill="#ffffff" d="M30.1 13.4 H33.9 L19.8 41.6 H16 Z" />
      <path fill="#ffffff" d="M30.1 13.4 H33.9 L48 41.6 H44.2 Z" />
      <rect x="22.4" y="32" width="19.2" height="3.5" fill="#ffffff" />
      <path
        fill="none"
        stroke="#ffffff"
        strokeWidth="3.3"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.3 47.4 H26.9 L29.8 44.5 L33.6 50.9 L36.8 47.4 H55.7"
      />
    </svg>
  );
}
