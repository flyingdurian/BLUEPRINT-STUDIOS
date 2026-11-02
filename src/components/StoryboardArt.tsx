import type { Shot } from '../types/studio'

// In-project vector animatic thumbnails: no external network dependencies or copyrighted art.
// All compositions share a simple reusable apartment, actor, phone and UI asset language.
export function StoryboardArt({shot, compact=false}:{shot:Shot,compact?:boolean}) {
  const key = shot.artKey
  const phoneScene = ['phone','call','chat','typing','notifications'].includes(key)
  const calm = ['mug','sofa'].includes(key)
  const isCall = key === 'call'
  const isPhoneFull = key==='chat'||key==='typing'
  return <svg className="story-illustration" viewBox="0 0 720 405" xmlns="http://www.w3.org/2000/svg" role="img" aria-label={`Illustrated placeholder for ${shot.code}: ${shot.notes}`} preserveAspectRatio="xMidYMid slice">
    <defs>
      <linearGradient id={`bg-${shot.id}`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#283d49"/><stop offset="1" stopColor="#192936"/></linearGradient>
      <linearGradient id={`lamp-${shot.id}`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#f3d9a5"/><stop offset="1" stopColor="#ae9475"/></linearGradient>
    </defs>
    <rect width="720" height="405" fill={`url(#bg-${shot.id})`}/>
    <path d="M0 288 L720 288 720 405 0 405Z" fill="#172733"/>
    <path d="M0 289 H720" stroke="#65828e" opacity=".3" strokeWidth="2"/>
    <rect x="497" y="42" width="157" height="171" rx="8" fill="#344e59" stroke="#5d7680" strokeWidth="6"/>
    <rect x="505" y="50" width="141" height="155" rx="3" fill="#6d8586" opacity=".38"/>
    <path d="M574 50 V205 M505 128 H646" stroke="#344c54" strokeWidth="6"/>
    <path d="M520 194 L565 142 L595 163 L646 108 V205 H505Z" fill="#729a97" opacity=".22"/>
    <rect x="50" y="196" width="280" height="115" rx="24" fill="#6d7171"/>
    <rect x="44" y="239" width="306" height="83" rx="20" fill="#737d7f"/>
    <rect x="59" y="262" width="122" height="54" rx="12" fill="#54686c"/>
    <rect x="195" y="262" width="139" height="54" rx="12" fill="#596a70"/>
    <rect x="70" y="321" width="16" height="34" rx="6" fill="#3c474b"/>
    <rect x="314" y="321" width="15" height="34" rx="6" fill="#3c474b"/>
    <rect x="430" y="309" width="190" height="18" rx="7" fill="#9a7862"/>
    <path d="M454 326 L449 376 M595 326 L604 376" stroke="#6e564b" strokeWidth="12" strokeLinecap="round"/>
    <ellipse cx="517" cy="381" rx="155" ry="13" fill="#0c1822" opacity=".42"/>
    <ellipse cx="238" cy="364" rx="131" ry="9" fill="#09151b" opacity=".36"/>
    {/* Scene-specific minimalist rig: geometric proportions + intentional facial pose */}
    {key==='restaurant' ? <>
      <rect x="260" y="242" width="219" height="132" rx="12" fill="#927866" stroke="#cba88b" strokeWidth="5"/>
      <text x="369" y="300" fill="#e9d7bb" fontFamily="system-ui" fontWeight="800" fontSize="19" textAnchor="middle">RESERVATIONS</text>
    </> : null}
    <path d="M206 287 Q198 253 206 218 L269 218 Q292 254 285 288Z" fill="#4c9992"/>
    <path d="M219 287 L209 352 M265 287 L273 352" stroke="#2d3648" strokeWidth="24" strokeLinecap="round"/>
    <path d="M207 232 L183 277 M277 232 L300 264" stroke="#4c9992" strokeWidth="24" strokeLinecap="round"/>
    <circle cx="240" cy="163" r="56" fill="#d39c77"/>
    <path d="M185 157 Q180 101 229 96 Q275 85 294 137 Q283 128 269 118 Q244 142 189 137Z" fill="#263944"/>
    <path d="M189 124 Q178 141 186 165" stroke="#263944" strokeWidth="12" strokeLinecap="round"/>
    <path d="M263 112 Q280 127 287 160" stroke="#263944" strokeWidth="14" strokeLinecap="round"/>
    {shot.mood==='shock' || shot.mood==='overwhelmed' || shot.mood==='chaos' ? <>
      <ellipse cx="220" cy="163" rx="6" ry="9" fill="#27343e"/><ellipse cx="258" cy="163" rx="6" ry="9" fill="#27343e"/>
      <ellipse cx="239" cy="193" rx="10" ry="14" fill="#704d46"/>
      <path d="M208 144 L228 137 M250 137 L271 144" stroke="#263944" strokeWidth="5"/>
    </> : <>
      <path d={calm?'M207 163 Q220 172 231 163 M246 163 Q258 172 270 163':'M213 162 L227 162 M250 162 L263 162'} stroke="#263944" strokeWidth="5" strokeLinecap="round"/>
      <path d={shot.mood==='relief'||shot.mood==='calm'||shot.mood==='peace'?'M223 193 Q239 207 256 191':'M225 195 Q239 190 253 195'} stroke="#744e45" strokeWidth="4" fill="none" strokeLinecap="round"/>
    </>}
    {key==='mug' || key==='sofa' ? <>
      <rect x="390" y="270" width="52" height="42" rx="6" fill="#e4c49c"/>
      <path d="M444 278 Q462 276 460 292 Q458 305 445 301" stroke="#e4c49c" strokeWidth="8" fill="none"/>
      <path d="M402 260 Q395 251 404 240 M418 260 Q411 248 421 237" stroke="#e3d6bc" opacity=".65" strokeWidth="3" fill="none"/>
    </> : null}
    {phoneScene || key==='drawer' || key==='badge' ? <g transform="translate(385 67) rotate(-5 110 140)">
      <rect x="65" y="32" width="171" height="244" rx="23" fill="#111a24" stroke="#67859b" strokeWidth="7"/>
      <rect x="74" y="44" width="153" height="219" rx="12" fill="#dfebde"/>
      <rect x="118" y="49" width="63" height="10" rx="5" fill="#172837"/>
      <rect x="84" y="73" width="132" height="28" rx="5" fill="#bbd2c6"/>
      <text x="150" y="91" fontSize="11" fontWeight="800" fill="#284750" textAnchor="middle" fontFamily="system-ui">{isCall?'AUNT CALLING':key==='typing'?'FAMILY GROUP':'MESSAGE THREAD'}</text>
      {isPhoneFull ? <>
        <rect x="88" y="120" width="107" height="24" rx="8" fill="#b4c7c3"/><rect x="106" y="152" width="108" height="25" rx="8" fill="#72a9a0"/>
        <rect x="88" y="185" width="100" height="23" rx="8" fill="#b4c7c3"/><rect x="98" y="220" width="116" height="25" rx="8" fill="#72a9a0"/>
      </> : <>
        <circle cx="149" cy="153" r="31" fill="#96b7b1"/><path d="M133 160 Q151 178 164 159" stroke="#29495a" strokeWidth="4" fill="none"/>
        <rect x="98" y="215" width="99" height="22" rx="11" fill={isCall?'#518c75':'#75a29d'}/>
      </>}
    </g> : null}
    {key==='notifications' && <g>
      {['THANK YOU!','83 NEW','YOU SAVED US'].map((t,i)=><g key={i} transform={`translate(${360+i*34},${42+i*72}) rotate(${i*4})`}><rect x="0" y="0" width="160" height="40" rx="12" fill="#cbd8cf"/><text x="80" y="26" textAnchor="middle" fontSize="16" fontWeight="800" fill="#345659">{t}</text></g>)}
    </g>}
    {key==='restaurant' && [50,130,570,645].map((x,i)=><g key={i} transform={`translate(${x} ${i%2===0?220:135})`}><rect width="60" height="88" rx="12" fill="#172b35" stroke="#8da7a6" strokeWidth="4"/><rect x="11" y="12" width="38" height="45" rx="3" fill="#a7c5c0"/><circle cx="30" cy="72" r="5" fill="#95b6b0"/></g>)}
    {key==='badge' && <g transform="rotate(-8 245 257)"><rect x="185" y="228" width="130" height="59" rx="4" fill="#e9bf80" stroke="#f3d69f" strokeWidth="4"/><text x="250" y="252" textAnchor="middle" fontFamily="system-ui" fontSize="13" fontWeight="800" fill="#25333b">DINNER</text><text x="250" y="269" textAnchor="middle" fontFamily="system-ui" fontSize="12" fontWeight="800" fill="#25333b">COORDINATOR</text></g>}
    <rect width="720" height="405" fill="none" stroke="#d6caab" strokeOpacity=".08" strokeWidth="6"/>
    {compact && <rect width="720" height="405" fill="#0c1219" opacity=".06"/>}
  </svg>
}
