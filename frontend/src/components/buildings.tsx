/** Flat-vector building illustrations for the town map (viewBox 0 0 160 100).
 * Each location id gets its own building; unknown ids get a generic cottage
 * tinted with the location's color. */

type Props = { locId: string; accent?: string };

const Shadow = () => <ellipse cx="80" cy="96" rx="62" ry="6" fill="rgba(0,0,0,0.18)" />;

function TownHall() {
  return (
    <>
      <Shadow />
      <rect x="28" y="46" width="104" height="48" fill="#e9e2cf" />
      <rect x="28" y="88" width="104" height="6" fill="#c9bfa4" />
      <polygon points="20,46 140,46 80,14" fill="#b8534a" />
      <polygon points="30,44 130,44 80,19" fill="#d8dbe4" />
      <rect x="76" y="4" width="3" height="14" fill="#8a8578" />
      <polygon points="79,5 100,9 79,13" fill="#3f7fd6" />
      {[40, 62, 96, 118].map((x) => (
        <rect key={x} x={x} y="50" width="8" height="38" fill="#f7f2e2" stroke="#c9bfa4" />
      ))}
      <rect x="72" y="60" width="16" height="28" rx="2" fill="#7a5636" />
      <circle cx="80" cy="38" r="6" fill="#f7f2e2" stroke="#c9bfa4" />
    </>
  );
}

function Tavern() {
  return (
    <>
      <Shadow />
      <rect x="34" y="42" width="92" height="52" fill="#f0dfb6" />
      <polygon points="26,44 134,44 118,16 42,16" fill="#8a5a33" />
      <rect x="34" y="42" width="92" height="5" fill="#6e4526" />
      {[48, 80, 112].map((x) => (
        <rect key={x} x={x - 2} y="42" width="4" height="52" fill="#6e4526" />
      ))}
      <rect x="44" y="54" width="16" height="14" fill="#ffd27f" stroke="#6e4526" />
      <rect x="100" y="54" width="16" height="14" fill="#ffd27f" stroke="#6e4526" />
      <rect x="70" y="62" width="20" height="32" rx="3" fill="#5d3a1e" />
      <line x1="126" y1="50" x2="140" y2="50" stroke="#6e4526" strokeWidth="3" />
      <rect x="132" y="52" width="14" height="14" rx="2" fill="#f7f2e2" stroke="#6e4526" />
      <text x="139" y="63" textAnchor="middle" fontSize="10">🍺</text>
    </>
  );
}

function Bakery() {
  return (
    <>
      <Shadow />
      <rect x="36" y="38" width="88" height="56" fill="#f5dfb0" />
      <polygon points="30,40 130,40 122,20 38,20" fill="#c98a5b" />
      <rect x="60" y="12" width="10" height="16" fill="#a8683f" />
      {[36, 51, 66, 81, 96, 111].map((x, i) => (
        <path key={x} d={`M${x} 46 h15 v10 a7.5 7.5 0 0 1 -15 0 z`} fill={i % 2 ? "#fff6e8" : "#e8564f"} />
      ))}
      <rect x="44" y="64" width="28" height="22" fill="#ffe9c4" stroke="#a8683f" />
      <text x="58" y="80" textAnchor="middle" fontSize="12">🥖</text>
      <rect x="88" y="60" width="18" height="34" rx="3" fill="#7a5636" />
    </>
  );
}

function Clinic() {
  return (
    <>
      <Shadow />
      <rect x="34" y="34" width="92" height="60" fill="#f4f6f4" />
      <rect x="30" y="28" width="100" height="10" rx="3" fill="#c7d4d2" />
      <rect x="70" y="42" width="20" height="20" rx="3" fill="#fff" stroke="#c7d4d2" />
      <rect x="77" y="45" width="6" height="14" fill="#d95b5b" />
      <rect x="73" y="49" width="14" height="6" fill="#d95b5b" />
      <rect x="44" y="66" width="14" height="14" fill="#cfe3ee" stroke="#c7d4d2" />
      <rect x="102" y="66" width="14" height="14" fill="#cfe3ee" stroke="#c7d4d2" />
      <rect x="72" y="68" width="16" height="26" rx="2" fill="#8fa8b8" />
    </>
  );
}

function Workshop() {
  return (
    <>
      <Shadow />
      <rect x="32" y="44" width="96" height="50" fill="#b06a3b" />
      <polygon points="24,46 136,46 80,14" fill="#5d4a3a" />
      <rect x="104" y="20" width="10" height="20" fill="#8a8578" />
      <circle cx="109" cy="14" r="4" fill="rgba(200,200,200,0.7)" />
      <circle cx="114" cy="7" r="3" fill="rgba(200,200,200,0.5)" />
      <rect x="62" y="58" width="36" height="36" fill="#6e4526" />
      <line x1="62" y1="58" x2="98" y2="94" stroke="#8a5a33" strokeWidth="3" />
      <line x1="98" y1="58" x2="62" y2="94" stroke="#8a5a33" strokeWidth="3" />
      <rect x="38" y="60" width="14" height="12" fill="#ffd27f" stroke="#6e4526" />
      <text x="112" y="80" textAnchor="middle" fontSize="13">⚙️</text>
    </>
  );
}

function GeneralStore() {
  return (
    <>
      <Shadow />
      <rect x="34" y="38" width="92" height="56" fill="#e3d7f5" />
      <rect x="30" y="30" width="100" height="10" rx="3" fill="#8a6cc9" />
      {[34, 50, 66, 82, 98, 114].map((x, i) => (
        <path key={x} d={`M${x} 44 h16 v9 a8 8 0 0 1 -16 0 z`} fill={i % 2 ? "#fff" : "#8a6cc9"} />
      ))}
      <rect x="42" y="62" width="26" height="20" fill="#fff" stroke="#b7a5dd" />
      <text x="55" y="77" textAnchor="middle" fontSize="11">🧺</text>
      <rect x="84" y="58" width="18" height="36" rx="3" fill="#6a54a0" />
      <rect x="108" y="76" width="14" height="12" fill="#c98a5b" stroke="#8a5a33" />
      <rect x="111" y="66" width="14" height="12" fill="#d9a06b" stroke="#8a5a33" />
    </>
  );
}

function Garden() {
  return (
    <>
      <Shadow />
      {[0, 1, 2].map((i) => (
        <g key={i}>
          <rect x={30 + i * 36} y="58" width="28" height="34" rx="3" fill="#7a5636" />
          <rect x={33 + i * 36} y="61" width="22" height="28" rx="2" fill="#5d4230" />
          <text x={44 + i * 36} y="80" textAnchor="middle" fontSize="12">{["🥕", "🌿", "🌻"][i]}</text>
        </g>
      ))}
      <rect x="24" y="46" width="112" height="5" rx="2" fill="#a8815c" />
      {[28, 52, 76, 100, 124].map((x) => (
        <rect key={x} x={x} y="38" width="5" height="16" rx="2" fill="#a8815c" />
      ))}
      <rect x="112" y="18" width="24" height="22" fill="#8a5a33" />
      <polygon points="108,20 140,20 124,6" fill="#6e4526" />
    </>
  );
}

function TownSquare() {
  return (
    <>
      <ellipse cx="80" cy="86" rx="70" ry="10" fill="#c9bfa4" opacity="0.6" />
      <ellipse cx="80" cy="82" rx="52" ry="12" fill="#9fc6d8" stroke="#7ba9be" strokeWidth="2" />
      <rect x="72" y="46" width="16" height="30" fill="#c4cdd6" />
      <ellipse cx="80" cy="46" rx="20" ry="6" fill="#9fc6d8" stroke="#7ba9be" strokeWidth="2" />
      <rect x="77" y="24" width="6" height="20" fill="#c4cdd6" />
      <path d="M80 24 q-14 8 -20 22" stroke="#bfe3f2" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M80 24 q14 8 20 22" stroke="#bfe3f2" strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle cx="80" cy="20" r="5" fill="#bfe3f2" />
    </>
  );
}

function Cottage({ accent = "#8ea3b8" }: { accent?: string }) {
  return (
    <>
      <Shadow />
      <rect x="40" y="44" width="80" height="50" fill="#efe6d2" />
      <polygon points="32,46 128,46 80,16" fill={accent} />
      <rect x="52" y="58" width="14" height="12" fill="#ffd27f" stroke="#b8ac90" />
      <rect x="94" y="58" width="14" height="12" fill="#ffd27f" stroke="#b8ac90" />
      <rect x="72" y="64" width="16" height="30" rx="2" fill="#7a5636" />
    </>
  );
}

const BUILDINGS: Record<string, () => React.ReactElement> = {
  town_hall: TownHall,
  tavern: Tavern,
  bakery: Bakery,
  clinic: Clinic,
  workshop: Workshop,
  general_store: GeneralStore,
  garden: Garden,
  town_square: TownSquare,
};

export function Building({ locId, accent }: Props) {
  const Illustration = BUILDINGS[locId];
  return (
    <svg viewBox="0 0 160 100" className="building" aria-hidden="true">
      {Illustration ? <Illustration /> : <Cottage accent={accent} />}
    </svg>
  );
}
