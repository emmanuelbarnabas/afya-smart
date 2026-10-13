// Nembo ya Afya Smart — kisanduku cha kijani + moyo mweupe wenye mstari wa ECG.
// Sawa kabisa na backend/app/static/logo.svg (SVG moja kwa moja = pixel-perfect,
// hakuna asset fetch). Duplicate ya dashboard/src/components/Logo.jsx kwa kuwa
// kila app ni Vite project tofauti (hakuna shared src).
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
      <path
        fill="#ffffff"
        d="M32 50 C21 42.5 15 35 15 27.5 C15 21.7 19.6 17 25.4 17 C28.7 17 31.2 18.7 32 21.4 C32.8 18.7 35.3 17 38.6 17 C44.4 17 49 21.7 49 27.5 C49 35 43 42.5 32 50 Z"
      />
      <path
        fill="none"
        stroke="url(#afyaLogoGrad)"
        stroke-width="4"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7 31 H19 L22.5 24 L26.5 39 L31 26.5 L34 31 H57"
      />
    </svg>
  );
}
