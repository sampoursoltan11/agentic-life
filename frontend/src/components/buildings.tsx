/** SimCity-style 2.5D building illustrations (viewBox 0 0 160 100).
 *
 * Shared style rules that keep the set coherent:
 *  - oblique projection: lit front face, darker side face offset (+12, -7)
 *  - light comes from the upper-left; roofs are the lightest surface
 *  - small animated details (smoke, flag, sign, water) carry the "alive" feel
 *    via CSS classes: .smoke, .flag, .sign-swing, .water-arc, .pool
 */

type Props = { locId: string; accent?: string };

const Shadow = ({ w = 62 }: { w?: number }) => (
  <ellipse cx="80" cy="95" rx={w} ry="5.5" fill="rgba(0,0,0,0.22)" />
);

/** Right-hand side face of a box building. */
function Side({ x, y, h, color, d = 12 }: { x: number; y: number; h: number; color: string; d?: number }) {
  return <polygon points={`${x},${y} ${x + d},${y - 7} ${x + d},${y + h - 7} ${x},${y + h}`} fill={color} />;
}

function Smoke({ x, y }: { x: number; y: number }) {
  return (
    <g className="smoke">
      <circle cx={x} cy={y} r="3.5" fill="rgba(210,210,215,0.8)" />
      <circle cx={x + 4} cy={y - 6} r="4.5" fill="rgba(210,210,215,0.6)" />
      <circle cx={x + 9} cy={y - 13} r="5.5" fill="rgba(210,210,215,0.4)" />
    </g>
  );
}

function Window({ x, y, w = 12, h = 11, lit = true }: { x: number; y: number; w?: number; h?: number; lit?: boolean }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="1.5" fill={lit ? "#ffd98c" : "#b8c7d6"} stroke="#5d4a3a" strokeWidth="1.4" />
      <line x1={x + w / 2} y1={y} x2={x + w / 2} y2={y + h} stroke="#5d4a3a" strokeWidth="0.9" />
      <line x1={x} y1={y + h / 2} x2={x + w} y2={y + h / 2} stroke="#5d4a3a" strokeWidth="0.9" />
      {lit && <rect x={x + 1} y={y + 1} width={w / 2 - 1.5} height={h / 2 - 1.5} fill="#fff3cf" opacity="0.8" />}
    </g>
  );
}

function TownHall() {
  return (
    <>
      <defs>
        <linearGradient id="th-roof" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e7ebf4" />
          <stop offset="1" stopColor="#b9c2d6" />
        </linearGradient>
      </defs>
      <Shadow w={66} />
      {/* steps */}
      <rect x="24" y="88" width="112" height="6" rx="2" fill="#c9c2ae" />
      <rect x="30" y="84" width="100" height="5" rx="2" fill="#d8d2c0" />
      {/* body + side */}
      <rect x="34" y="44" width="92" height="42" fill="#efe9d6" />
      <Side x={126} y={44} h={42} color="#c9c0a4" />
      {/* pediment */}
      <polygon points="28,44 132,44 80,16" fill="url(#th-roof)" stroke="#9aa3ba" strokeWidth="1.5" />
      <polygon points="132,44 144,37 92,11 80,16" fill="#a8b1c8" />
      <circle cx="80" cy="33" r="6.5" fill="#f7d774" stroke="#b8963f" strokeWidth="1.5" />
      {/* columns */}
      {[42, 62, 92, 112].map((x) => (
        <g key={x}>
          <rect x={x} y="48" width="9" height="36" fill="#faf5e6" stroke="#c9c0a4" strokeWidth="1" />
          <rect x={x - 1.5} y="46" width="12" height="3.5" fill="#e3dcc6" />
          <rect x={x - 1.5} y="82" width="12" height="3.5" fill="#e3dcc6" />
        </g>
      ))}
      {/* door */}
      <rect x="73" y="58" width="15" height="26" rx="2" fill="#6e4526" />
      <rect x="75.5" y="61" width="10" height="10" rx="1" fill="#8a5f38" />
      {/* flag */}
      <rect x="78.5" y="0" width="2.5" height="17" fill="#8a8578" />
      <polygon className="flag" points="81,2 102,5.5 81,10" fill="#3f7fd6" />
    </>
  );
}

function Tavern() {
  return (
    <>
      <Shadow />
      {/* body + side */}
      <rect x="34" y="40" width="88" height="54" fill="#f0dfb6" />
      <Side x={122} y={40} h={54} color="#cdb98c" />
      {/* roof: shingled gable */}
      <polygon points="26,42 130,42 112,14 44,14" fill="#8a5a33" />
      <polygon points="130,42 142,35 124,9 112,14" fill="#6e4526" />
      {[22, 30, 38].map((y) => (
        <line key={y} x1={30 + (42 - y) * 0.6} y1={y} x2={126 - (42 - y) * 0.6} y2={y} stroke="#6e4526" strokeWidth="1.2" />
      ))}
      {/* timber frame */}
      <rect x="34" y="40" width="88" height="4" fill="#6e4526" />
      {[48, 78, 108].map((x) => (
        <rect key={x} x={x} y="40" width="3.5" height="54" fill="#6e4526" />
      ))}
      <line x1="36" y1="70" x2="120" y2="70" stroke="#6e4526" strokeWidth="2.5" />
      <Window x={56} y={50} />
      <Window x={92} y={50} />
      {/* door + lantern */}
      <rect x="68" y="62" width="19" height="32" rx="3" fill="#5d3a1e" />
      <circle cx="83" cy="78" r="1.6" fill="#f7d774" />
      <circle cx="60" cy="60" r="2.5" fill="#ffd98c" stroke="#6e4526" />
      {/* swinging sign */}
      <line x1="122" y1="48" x2="140" y2="48" stroke="#6e4526" strokeWidth="3" strokeLinecap="round" />
      <g className="sign-swing">
        <line x1="134" y1="48" x2="134" y2="53" stroke="#6e4526" strokeWidth="1.5" />
        <rect x="126" y="53" width="17" height="15" rx="2.5" fill="#f7f2e2" stroke="#6e4526" strokeWidth="1.5" />
        <text x="134.5" y="65" textAnchor="middle" fontSize="10">🍺</text>
      </g>
    </>
  );
}

function Bakery() {
  return (
    <>
      <Shadow />
      <rect x="34" y="36" width="90" height="58" fill="#f5dfb0" />
      <Side x={124} y={36} h={58} color="#d6bd85" />
      {/* flat roof + parapet */}
      <rect x="30" y="30" width="98" height="9" rx="2" fill="#c98a5b" />
      <polygon points="128,30 140,23 140,32 128,39" fill="#a8683f" />
      {/* chimney + smoke */}
      <rect x="108" y="12" width="11" height="20" fill="#a8683f" />
      <rect x="106" y="9" width="15" height="5" rx="1" fill="#8a5636" />
      <Smoke x={113} y={4} />
      {/* scalloped awning */}
      {[36, 51, 66, 81, 96, 111].map((x, i) => (
        <path key={x} d={`M${x} 44 h15 v9 a7.5 7.5 0 0 1 -15 0 z`} fill={i % 2 ? "#fff6e8" : "#e8564f"} stroke="#c9443e" strokeWidth="0.8" />
      ))}
      {/* display window with goods */}
      <rect x="42" y="62" width="34" height="24" rx="2" fill="#ffe9c4" stroke="#a8683f" strokeWidth="1.5" />
      <rect x="42" y="80" width="34" height="6" fill="#c98a5b" />
      <text x="52" y="77" textAnchor="middle" fontSize="10">🥖</text>
      <text x="66" y="77" textAnchor="middle" fontSize="9">🥐</text>
      {/* door + sign */}
      <rect x="88" y="60" width="18" height="34" rx="3" fill="#7a5636" />
      <circle cx="102" cy="77" r="1.5" fill="#f7d774" />
      <rect x="80" y="20" width="30" height="9" rx="4.5" fill="#fff6e8" stroke="#c98a5b" strokeWidth="1.2" />
      <text x="95" y="27" textAnchor="middle" fontSize="6.5" fontWeight="bold" fill="#8a5636">BAKERY</text>
    </>
  );
}

function Clinic() {
  return (
    <>
      <Shadow />
      <rect x="32" y="34" width="94" height="60" fill="#f4f7f7" />
      <Side x={126} y={34} h={60} color="#c9d6d4" />
      <rect x="28" y="28" width="102" height="8" rx="2" fill="#dae5e3" />
      <polygon points="130,28 142,21 142,29 130,36" fill="#b9c9c6" />
      {/* rooftop cross sign */}
      <rect x="66" y="8" width="26" height="22" rx="3" fill="#fff" stroke="#c9d6d4" strokeWidth="1.5" />
      <rect x="76" y="11" width="6" height="16" fill="#e04a4a" />
      <rect x="71" y="16" width="16" height="6" fill="#e04a4a" />
      <Window x={40} y={44} lit={false} />
      <Window x={100} y={44} lit={false} />
      <Window x={40} y={66} lit={false} />
      <Window x={100} y={66} lit={false} />
      {/* entrance with canopy */}
      <rect x="66" y="58" width="26" height="36" rx="2" fill="#9fc0d4" stroke="#7ba3bc" strokeWidth="1.5" />
      <line x1="79" y1="58" x2="79" y2="94" stroke="#7ba3bc" strokeWidth="1.5" />
      <rect x="60" y="52" width="38" height="7" rx="3" fill="#e04a4a" />
    </>
  );
}

function Workshop() {
  return (
    <>
      <Shadow />
      {/* barn body + side */}
      <rect x="30" y="42" width="94" height="52" fill="#b06a3b" />
      <Side x={124} y={42} h={52} color="#8a4f28" />
      {[52, 66, 80, 94].map((y) => (
        <line key={y} x1="31" y1={y} x2="123" y2={y} stroke="#9a5a30" strokeWidth="1.4" />
      ))}
      {/* gambrel-ish roof */}
      <polygon points="22,44 134,44 80,12" fill="#5d4a3a" />
      <polygon points="134,44 146,37 92,7 80,12" fill="#493a2e" />
      <line x1="42" y1="33" x2="118" y2="33" stroke="#493a2e" strokeWidth="1.4" />
      {/* chimney + smoke */}
      <rect x="102" y="16" width="11" height="20" fill="#8a8578" />
      <rect x="100" y="13" width="15" height="4.5" rx="1" fill="#6f6b60" />
      <Smoke x={107} y={8} />
      {/* big X door */}
      <rect x="58" y="56" width="40" height="38" fill="#6e4526" stroke="#5d3a1e" strokeWidth="2" />
      <line x1="58" y1="56" x2="98" y2="94" stroke="#8a5a33" strokeWidth="3.5" />
      <line x1="98" y1="56" x2="58" y2="94" stroke="#8a5a33" strokeWidth="3.5" />
      <Window x={38} y={58} w={13} h={11} />
      {/* gear sign + anvil */}
      <circle cx="112" cy="64" r="8" fill="#d8d2c0" stroke="#5d4a3a" strokeWidth="1.5" />
      <text x="112" y="68" textAnchor="middle" fontSize="9">⚙️</text>
      <text x="40" y="91" textAnchor="middle" fontSize="9">🪨</text>
    </>
  );
}

function GeneralStore() {
  return (
    <>
      <Shadow />
      <rect x="32" y="36" width="92" height="58" fill="#e9def7" />
      <Side x={124} y={36} h={58} color="#c3b1e0" />
      <rect x="28" y="29" width="100" height="9" rx="2" fill="#8a6cc9" />
      <polygon points="128,29 140,22 140,31 128,38" fill="#6f54a6" />
      {/* awning */}
      {[34, 50, 66, 82, 98, 114].map((x, i) => (
        <path key={x} d={`M${x} 44 h16 v8 a8 8 0 0 1 -16 0 z`} fill={i % 2 ? "#fff" : "#8a6cc9"} stroke="#6f54a6" strokeWidth="0.8" />
      ))}
      {/* shop window with goods */}
      <rect x="40" y="60" width="30" height="22" rx="2" fill="#fff" stroke="#b7a5dd" strokeWidth="1.5" />
      <text x="49" y="76" textAnchor="middle" fontSize="9">🧺</text>
      <text x="62" y="76" textAnchor="middle" fontSize="8">🍎</text>
      <rect x="40" y="78" width="30" height="4" fill="#b7a5dd" />
      {/* door */}
      <rect x="82" y="58" width="18" height="36" rx="3" fill="#6a54a0" />
      <circle cx="96" cy="76" r="1.5" fill="#f7d774" />
      {/* crates out front */}
      <rect x="106" y="76" width="15" height="13" fill="#c98a5b" stroke="#8a5a33" strokeWidth="1.2" />
      <rect x="109" y="65" width="15" height="12" fill="#d9a06b" stroke="#8a5a33" strokeWidth="1.2" />
      <line x1="106" y1="82" x2="121" y2="82" stroke="#8a5a33" />
      <rect x="76" y="18" width="34" height="9" rx="4.5" fill="#fff" stroke="#8a6cc9" strokeWidth="1.2" />
      <text x="93" y="25" textAnchor="middle" fontSize="6" fontWeight="bold" fill="#6f54a6">GENERAL</text>
    </>
  );
}

function Garden() {
  return (
    <>
      <Shadow w={68} />
      {/* greenhouse */}
      <rect x="106" y="34" width="38" height="28" fill="rgba(190,228,235,0.75)" stroke="#7ba9be" strokeWidth="1.5" />
      <polygon points="102,36 148,36 125,18" fill="rgba(210,240,246,0.85)" stroke="#7ba9be" strokeWidth="1.5" />
      <line x1="115" y1="36" x2="115" y2="62" stroke="#7ba9be" />
      <line x1="134" y1="36" x2="134" y2="62" stroke="#7ba9be" />
      <text x="124" y="55" textAnchor="middle" fontSize="10">🍅</text>
      {/* raised beds */}
      {[0, 1, 2].map((i) => (
        <g key={i}>
          <rect x={16 + i * 30} y="66" width="26" height="26" rx="3" fill="#8a5a33" />
          <rect x={18 + i * 30} y="63" width="26" height="26" rx="3" fill="#a8734a" />
          <rect x={21 + i * 30} y="66" width="20" height="20" rx="2" fill="#5d4230" />
          <text x={31 + i * 30} y="81" textAnchor="middle" fontSize="11">{["🥕", "🌿", "🌻"][i]}</text>
        </g>
      ))}
      {/* fence */}
      <rect x="10" y="46" width="88" height="4" rx="2" fill="#c9a06b" />
      {[14, 34, 54, 74, 92].map((x) => (
        <g key={x}>
          <rect x={x} y="38" width="4.5" height="16" rx="2" fill="#c9a06b" />
          <rect x={x + 0.8} y="38" width="1.6" height="16" fill="#a8815c" />
        </g>
      ))}
      <text x="102" y="93" textAnchor="middle" fontSize="9">🦋</text>
    </>
  );
}

function TownSquare() {
  return (
    <>
      {/* cobblestone plaza */}
      <ellipse cx="80" cy="78" rx="74" ry="19" fill="#cfc7b0" />
      <ellipse cx="80" cy="77" rx="66" ry="16" fill="#ded6bd" />
      {[[30, 76], [46, 84], [66, 88], [92, 87], [114, 83], [126, 75], [56, 72], [104, 72]].map(([x, y]) => (
        <ellipse key={`${x}${y}`} cx={x} cy={y} rx="5" ry="2.2" fill="#c4bba0" />
      ))}
      {/* fountain */}
      <ellipse className="pool" cx="80" cy="72" rx="34" ry="11" fill="#8fc6dd" stroke="#6f9fb5" strokeWidth="2" />
      <ellipse cx="80" cy="70" rx="26" ry="7.5" fill="#a9d8ea" />
      <rect x="72" y="42" width="16" height="26" fill="#cfd6de" />
      <Side x={88} y={42} h={26} color="#a9b2be" d={7} />
      <ellipse cx="80" cy="42" rx="17" ry="5" fill="#9fc6d8" stroke="#7ba9be" strokeWidth="1.5" />
      <rect x="77" y="20" width="6" height="20" fill="#cfd6de" />
      <path className="water-arc" d="M80 20 q-16 9 -22 26" stroke="#cfeaf5" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path className="water-arc water-arc--late" d="M80 20 q16 9 22 26" stroke="#cfeaf5" strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle cx="80" cy="17" r="4.5" fill="#e8f6fb" stroke="#a9d8ea" />
      {/* lamp posts */}
      {[26, 134].map((x) => (
        <g key={x}>
          <rect x={x - 1.5} y="46" width="3" height="26" fill="#494f5c" />
          <circle cx={x} cy="43" r="4.5" fill="#ffe9a8" stroke="#494f5c" strokeWidth="1.5" />
        </g>
      ))}
      {/* bench */}
      <rect x="38" y="58" width="20" height="3.5" rx="1.5" fill="#8a5a33" />
      <rect x="40" y="61" width="3" height="6" fill="#6e4526" />
      <rect x="53" y="61" width="3" height="6" fill="#6e4526" />
    </>
  );
}

function Residences() {
  return (
    <>
      <Shadow w={70} />
      {/* back cottage (slightly recessed) */}
      <g opacity="0.92">
        <rect x="96" y="40" width="40" height="38" fill="#dfe6d0" />
        <Side x={136} y={40} h={38} color="#b8c2a6" d={10} />
        <polygon points="90,42 142,42 116,20" fill="#4a7fb5" />
        <polygon points="142,42 152,36 126,15 116,20" fill="#3a6591" />
        <Window x={104} y={50} w={10} h={9} />
        <rect x="120" y="58" width="10" height="20" rx="2" fill="#7a5636" />
      </g>
      {/* front-left cottage */}
      <rect x="16" y="48" width="42" height="44" fill="#f0dfb6" />
      <Side x={58} y={48} h={44} color="#cdb98c" d={10} />
      <polygon points="10,50 64,50 37,26" fill="#b8534a" />
      <polygon points="64,50 74,44 47,21 37,26" fill="#943f38" />
      <rect x="44" y="30" width="7" height="14" fill="#a8683f" />
      <Smoke x={48} y={24} />
      <Window x={22} y={58} w={11} h={10} />
      <rect x="38" y="64" width="12" height="28" rx="2" fill="#7a5636" />
      {/* front-middle cottage */}
      <rect x="62" y="54" width="38" height="38" fill="#e8d3c4" />
      <Side x={100} y={54} h={38} color="#c4ab97" d={10} />
      <polygon points="56,56 106,56 81,34" fill="#8a6cc9" />
      <polygon points="106,56 116,50 91,29 81,34" fill="#6f54a6" />
      <Window x={68} y={62} w={10} h={9} />
      <rect x="82" y="66" width="11" height="26" rx="2" fill="#6a5140" />
      {/* garden touches */}
      <circle cx="10" cy="88" r="6" fill="#6fae62" />
      <circle cx="148" cy="86" r="7" fill="#5f9e54" />
      <text x="60" y="97" textAnchor="middle" fontSize="7">🌷</text>
    </>
  );
}

function Cottage({ accent = "#8ea3b8" }: { accent?: string }) {
  return (
    <>
      <Shadow />
      <rect x="38" y="44" width="80" height="50" fill="#efe6d2" />
      <Side x={118} y={44} h={50} color="#cfc4a8" />
      <polygon points="30,46 126,46 78,16" fill={accent} />
      <polygon points="126,46 138,39 90,11 78,16" fill="rgba(0,0,0,0.25)" />
      <Window x={48} y={56} />
      <Window x={92} y={56} />
      <rect x="70" y="62" width="16" height="32" rx="2" fill="#7a5636" />
    </>
  );
}

const BUILDINGS: Record<string, () => React.ReactElement> = {
  residences: Residences,
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

/** Decorative nature clusters for empty map cells — trees, bushes, flowers. */
export function Decor({ x, y, variant }: { x: number; y: number; variant: number }) {
  const tree = (tx: number, ty: number, s: number, dark = false) => (
    <g transform={`translate(${tx},${ty}) scale(${s})`}>
      <ellipse cx="0" cy="26" rx="13" ry="3.5" fill="rgba(0,0,0,0.15)" />
      <rect x="-2.5" y="12" width="5" height="14" fill="#8a5a33" />
      <circle cx="0" cy="4" r="11" fill={dark ? "#4a8a42" : "#5fa653"} />
      <circle cx="-7" cy="10" r="8" fill={dark ? "#3f7a38" : "#529546"} />
      <circle cx="7" cy="10" r="8" fill={dark ? "#55984c" : "#6db35f"} />
      <circle cx="-3" cy="1" r="4" fill="rgba(255,255,255,0.18)" />
    </g>
  );
  const pine = (tx: number, ty: number, s: number) => (
    <g transform={`translate(${tx},${ty}) scale(${s})`}>
      <ellipse cx="0" cy="27" rx="11" ry="3" fill="rgba(0,0,0,0.15)" />
      <rect x="-2" y="18" width="4" height="9" fill="#7a5636" />
      <polygon points="-11,20 11,20 0,4" fill="#3f7a4a" />
      <polygon points="-9,12 9,12 0,-2" fill="#4a8a56" />
      <polygon points="-7,4 7,4 0,-8" fill="#55984f" />
    </g>
  );
  const bush = (tx: number, ty: number) => (
    <g transform={`translate(${tx},${ty})`}>
      <ellipse cx="0" cy="6" rx="10" ry="2.5" fill="rgba(0,0,0,0.12)" />
      <circle cx="-5" cy="0" r="6" fill="#5fa653" />
      <circle cx="4" cy="1" r="5" fill="#6db35f" />
      <circle cx="0" cy="-3" r="5" fill="#7dbf6e" />
    </g>
  );
  const flowers = (tx: number, ty: number) => (
    <g transform={`translate(${tx},${ty})`}>
      {[[0, 0, "#e87ba4"], [9, 4, "#f7d774"], [-8, 5, "#e8564f"], [3, 9, "#b78ef5"]].map(([fx, fy, c]) => (
        <circle key={`${fx}${fy}`} cx={fx as number} cy={fy as number} r="2.2" fill={c as string} />
      ))}
    </g>
  );
  const rock = (tx: number, ty: number) => (
    <g transform={`translate(${tx},${ty})`}>
      <ellipse cx="0" cy="3" rx="8" ry="2" fill="rgba(0,0,0,0.12)" />
      <ellipse cx="0" cy="0" rx="7" ry="4.5" fill="#a8a394" />
      <ellipse cx="-2" cy="-1.5" rx="3" ry="1.6" fill="#c2bdae" />
    </g>
  );

  const variants = [
    <>
      {tree(x + 40, y + 40, 1.15)}
      {tree(x + 95, y + 70, 0.85, true)}
      {bush(x + 130, y + 45)}
      {flowers(x + 70, y + 105)}
    </>,
    <>
      {pine(x + 55, y + 45, 1.2)}
      {pine(x + 105, y + 75, 0.9)}
      {rock(x + 35, y + 100)}
      {flowers(x + 130, y + 95)}
    </>,
    <>
      {tree(x + 110, y + 45, 1.0)}
      {bush(x + 45, y + 65)}
      {bush(x + 75, y + 100)}
      {flowers(x + 120, y + 110)}
      {rock(x + 145, y + 70)}
    </>,
  ];
  return variants[variant % variants.length];
}
