// Nembo ya maneno (wordmark) "Afya Smart" + pulse accent chini.
// Inachukua maandishi ya h1 kwenye header — jina lenyeye ndilo logo.
// Duplicate ya dashboard/src/components/Logo.jsx kwa kuwa kila app ni
// Vite project tofauti (hakuna shared src).
export default function Logo({ height = 36, className }) {
  const width = Math.round((height * 300) / 62);
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 300 62"
      className={className}
      style={{ display: "block" }}
      role="img"
      aria-label="Afya Smart"
    >
      <text
        x="150"
        y="40"
        textAnchor="middle"
        textLength="284"
        lengthAdjust="spacingAndGlyphs"
        fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"
        fontSize="40"
        fontWeight="800"
      >
        <tspan fill="#085c39">Afya</tspan>
        <tspan fill="#16a066"> Smart</tspan>
      </text>
      <path
        fill="none"
        stroke="#16a066"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 54 H188 L197 50 L206 58 L215 54 H292"
      />
    </svg>
  );
}
