import React, { useState, useEffect, useRef } from "react";

// ─── CSS keyframes injected once ──────────────────────────────────────────────
let _stylesInjected = false;
function ensureStyles() {
  if (_stylesInjected || typeof document === "undefined") return;
  _stylesInjected = true;
  const el = document.createElement("style");
  el.textContent = `
    .bk-wrap { display:flex; flex-direction:column; align-items:center; margin-bottom:20px; user-select:none; }
    .bk-scene { position:relative; width:160px; height:190px; display:flex; align-items:center; justify-content:center; }

    @keyframes bkFloat {
      0%,100% { transform: translateY(0px) rotate(0deg); }
      50%      { transform: translateY(-8px) rotate(-1deg); }
    }
    @keyframes bkIdleGlow {
      0%,100% { filter: drop-shadow(0 0 10px rgba(56,189,248,.30)); }
      50%      { filter: drop-shadow(0 0 22px rgba(56,189,248,.65)); }
    }
    @keyframes bkLoadBob {
      0%,100% { transform: translateY(0px) scale(1); }
      50%      { transform: translateY(-5px) scale(1.04); }
    }
    @keyframes bkLoadGlow {
      0%,100% { filter: drop-shadow(0 0 10px rgba(245,158,11,.40)); }
      50%      { filter: drop-shadow(0 0 26px rgba(245,158,11,.85)); }
    }
    @keyframes bkShake {
      0%   { transform: translateX(0) rotate(0deg); }
      10%  { transform: translateX(-9px) rotate(-2.5deg); }
      20%  { transform: translateX(9px)  rotate(2.5deg); }
      30%  { transform: translateX(-7px) rotate(-2deg); }
      40%  { transform: translateX(7px)  rotate(2deg); }
      50%  { transform: translateX(-5px) rotate(-1.5deg); }
      60%  { transform: translateX(5px)  rotate(1.5deg); }
      70%  { transform: translateX(-3px) rotate(-1deg); }
      80%  { transform: translateX(3px)  rotate(1deg); }
      90%  { transform: translateX(-1px); }
      100% { transform: translateX(0) rotate(0deg); }
    }
    @keyframes bkErrorGlow {
      0%,100% { filter: drop-shadow(0 0 8px rgba(239,68,68,.35)); }
      35%      { filter: drop-shadow(0 0 26px rgba(239,68,68,.90)) drop-shadow(0 0 46px rgba(239,68,68,.40)); }
    }
    @keyframes bkCoverOpen {
      0%   { transform: translateX(0px)   translateY(0px)  rotate(0deg);  opacity: 1;   }
      18%  { transform: translateX(-8px)  translateY(-4px) rotate(-3deg); opacity: 0.98; }
      55%  { transform: translateX(-70px) translateY(-4px) rotate(-7deg); opacity: 0.15; }
      100% { transform: translateX(-95px) translateY(-4px) rotate(-9deg); opacity: 0;   }
    }
    @keyframes bkPagesReveal {
      0%   { opacity: 0; }
      30%  { opacity: 0; }
      70%  { opacity: 0.85; }
      100% { opacity: 1; }
    }
    @keyframes bkPageGlow {
      0%   { filter: drop-shadow(0 0 4px  rgba(168,85,247,.2)); }
      50%  { filter: drop-shadow(0 0 22px rgba(168,85,247,.9)) drop-shadow(0 0 40px rgba(251,191,36,.5)); }
      100% { filter: drop-shadow(0 0 14px rgba(168,85,247,.5)); }
    }
    @keyframes bkSuccessGlow {
      0%   { filter: drop-shadow(0 0 12px rgba(168,85,247,.50)); }
      50%  { filter: drop-shadow(0 0 28px rgba(168,85,247,1.00)) drop-shadow(0 0 52px rgba(56,189,248,.60)); }
      100% { filter: drop-shadow(0 0 16px rgba(168,85,247,.55)); }
    }
    @keyframes bkSpark {
      0%   { opacity:1; transform:translate(0,0) scale(1) rotate(0deg); }
      100% { opacity:0; transform:translate(var(--sx),var(--sy)) scale(0) rotate(200deg); }
    }
    @keyframes bkOrbit {
      from { transform: rotate(0deg)   translateX(52px) rotate(0deg); }
      to   { transform: rotate(360deg) translateX(52px) rotate(-360deg); }
    }
    @keyframes bkRing {
      0%   { stroke-dashoffset:314; opacity:0.8; transform:scale(0.4) rotate(-20deg); }
      100% { stroke-dashoffset:0;   opacity:0;   transform:scale(1.7) rotate(70deg); }
    }

    /* ── Register: book unfolds from center outward ── */
    @keyframes bkBookOpenIn {
      0%   { transform: scaleX(0.06) scaleY(0.80); opacity: 0; }
      45%  { transform: scaleX(1.04) scaleY(1.02); opacity: 1; }
      72%  { transform: scaleX(0.99) scaleY(1.00); }
      100% { transform: scaleX(1)    scaleY(1);    opacity: 1; }
    }
    /* ── Form fades out when switching to register ── */
    @keyframes bkFadeOut {
      0%   { opacity:1; transform:translateY(0); }
      100% { opacity:0; transform:translateY(-12px); }
    }
    /* ── Generic form fade-in ── */
    @keyframes bkFormIn {
      from { opacity:0; transform:translateY(14px); }
      to   { opacity:1; transform:translateY(0); }
    }
    .bk-form-in { animation: bkFormIn 0.5s ease-out both; }

    @keyframes bkLabelPulse {
      0%,100% { opacity:0.55; letter-spacing:0.14em; }
      50%      { opacity:1.00; letter-spacing:0.20em; }
    }
    .bk-label {
      font-size:0.68rem; font-weight:700; text-transform:uppercase;
      margin-top:10px; animation:bkLabelPulse 1.8s infinite;
    }

    /* ── Open book page input style ── */
    .bk-page-input {
      width:100%; background:rgba(56,189,248,0.06);
      border:1px solid rgba(56,189,248,0.40); border-radius:4px;
      padding:6px 8px; color:var(--text-1); font-size:0.83rem;
      outline:none; box-sizing:border-box; transition:border-color .2s;
    }
    .bk-page-input:focus { border-color:rgba(56,189,248,0.85); }
    .bk-page-input:disabled { opacity:0.5; }
    .bk-page-input.err { border-color:rgba(239,68,68,0.70); }
    .bk-page-label {
      display:block; font-size:0.62rem; font-weight:600;
      letter-spacing:0.08em; margin-bottom:4px; opacity:0.65;
    }
  `;
  document.head.appendChild(el);
}

// ─── Sparkle particle ────────────────────────────────────────────────────────
function Spark({ angle, dist, size, color, delay, shape = "circle" }) {
  const rad = (angle * Math.PI) / 180;
  const base = {
    position: "absolute", left: "50%", top: "50%",
    width: size, height: size,
    marginLeft: -size / 2, marginTop: -size / 2,
    animation: `bkSpark ${0.55 + delay * 0.3}s ${delay}s cubic-bezier(.2,.8,.4,1) forwards`,
    "--sx": `${(Math.cos(rad) * dist).toFixed(1)}px`,
    "--sy": `${(Math.sin(rad) * dist).toFixed(1)}px`,
    pointerEvents: "none",
  };
  if (shape === "star")
    return <div style={{ ...base, display:"flex", alignItems:"center", justifyContent:"center", color, fontSize:size*1.6, lineHeight:1, background:"none" }}>✦</div>;
  if (shape === "diamond")
    return <div style={{ ...base, display:"flex", alignItems:"center", justifyContent:"center", color, fontSize:size*1.4, lineHeight:1, background:"none" }}>◆</div>;
  return <div style={{ ...base, background:color, borderRadius:"50%", boxShadow:`0 0 ${size*2}px ${color}` }} />;
}

// ─── Orbit dot (loading) ─────────────────────────────────────────────────────
function OrbitDot({ delay, color }) {
  return (
    <div style={{ position:"absolute", left:"50%", top:"50%", width:6, height:6, marginLeft:-3, marginTop:-3, animation:`bkOrbit 1.4s ${delay}s linear infinite` }}>
      <div style={{ width:"100%", height:"100%", background:color, borderRadius:"50%", boxShadow:`0 0 8px ${color}` }} />
    </div>
  );
}

// ─── SVG Book ─────────────────────────────────────────────────────────────────
function BookSVG({ state }) {
  const isError   = state === "error";
  const isSuccess = state === "success";
  const isLoading = state === "loading";
  const isOpening = state === "opening"; // register transition — cover opens, no pages

  const accent  = isError ? "#ef4444" : isSuccess ? "#a855f7" : isLoading ? "#f59e0b" : "#38bdf8";
  const accent2 = isError ? "#b91c1c" : isSuccess ? "#7c3aed" : isLoading ? "#d97706" : "#0284c7";
  const bg      = isError ? "#1a0505" : isSuccess ? "#100820" : "#070f1c";
  const bg2     = isError ? "#0a0000" : isSuccess ? "#060010" : "#030810";

  const mainAnim =
    isError   ? "bkShake 0.80s ease-out, bkErrorGlow 0.80s ease-out"
  : isSuccess ? "bkSuccessGlow 2s ease-in-out infinite"
  : isLoading ? "bkLoadBob 0.9s ease-in-out infinite, bkLoadGlow 0.9s ease-in-out infinite"
  :             "bkFloat 3.2s ease-in-out infinite, bkIdleGlow 3.2s ease-in-out infinite";

  // Cover opens for both success and register-transition (opening)
  const coverAnim = isSuccess
    ? "bkCoverOpen 0.70s 0.05s cubic-bezier(.55,0,.45,1) forwards"
    : isOpening
    ? "bkCoverOpen 0.60s ease-in-out forwards"
    : "none";

  // Pages only revealed on actual success (not register transition)
  const pagesAnim = isSuccess
    ? "bkPagesReveal 0.75s 0.10s ease-out forwards, bkPageGlow 2s 0.55s ease-in-out infinite"
    : "none";

  return (
    <svg viewBox="0 0 100 130" width="100" height="130" style={{ animation: mainAnim, overflow: "visible" }}>
      <defs>
        <linearGradient id="bkBg"     x1="0%" y1="0%"  x2="100%" y2="100%"><stop offset="0%"   stopColor={bg}     /><stop offset="100%" stopColor={bg2}    /></linearGradient>
        <linearGradient id="bkSpine"  x1="0%" y1="0%"  x2="100%" y2="0%"  ><stop offset="0%"   stopColor={accent2} stopOpacity="1" /><stop offset="100%" stopColor={accent}  stopOpacity="0.5" /></linearGradient>
        <linearGradient id="bkMagic"  x1="0%" y1="0%"  x2="0%"   y2="100%"><stop offset="0%"   stopColor="#fbbf24" stopOpacity="0.7" /><stop offset="45%"  stopColor="#a855f7" stopOpacity="0.9" /><stop offset="100%" stopColor="#38bdf8" stopOpacity="0.6" /></linearGradient>
        <linearGradient id="bkPage"   x1="0%" y1="0%"  x2="100%" y2="100%"><stop offset="0%"   stopColor="#f8f4ec" /><stop offset="100%" stopColor="#e5d9c4" /></linearGradient>
      </defs>

      {/* Open pages — only relevant for success */}
      <g style={{ opacity: 0, animation: pagesAnim }}>
        <rect x="13" y="13" width="35" height="104" rx="2" fill="url(#bkPage)" opacity="0.12" />
        <rect x="52" y="13" width="35" height="104" rx="2" fill="url(#bkPage)" opacity="0.12" />
        <rect x="47" y="13" width="6"  height="104" fill={accent2} opacity="0.45" />
        <ellipse cx="50" cy="65" rx="24" ry="42" fill="url(#bkMagic)" opacity="0.30" />
        {[30,40,50,60,70,80,90,100].map(y => <line key={`l${y}`} x1="18" y1={y} x2="43" y2={y} stroke={accent} strokeWidth="1" opacity="0.22" />)}
        {[30,40,50,60,70,80,90,100].map(y => <line key={`r${y}`} x1="57" y1={y} x2="82" y2={y} stroke={accent} strokeWidth="1" opacity="0.22" />)}
        <circle cx="30" cy="65" r="11" fill="none" stroke={accent} strokeWidth="1.2" opacity="0.40" />
        <line x1="30" y1="54" x2="30" y2="76" stroke={accent} strokeWidth="1" opacity="0.30" />
        <line x1="19" y1="65" x2="41" y2="65" stroke={accent} strokeWidth="1" opacity="0.30" />
        <text x="70" y="70" textAnchor="middle" fill={accent} fontSize="15" opacity="0.45" style={{ fontFamily:"serif" }}>✦</text>
      </g>

      {/* Closed front cover */}
      <g style={{ animation: coverAnim }}>
        <rect x="84" y="17" width="3" height="96" rx="1" fill={accent} opacity="0.18" />
        <rect x="82" y="18" width="3" height="94" rx="1" fill={accent} opacity="0.12" />
        <rect x="80" y="19" width="3" height="92" rx="1" fill={accent} opacity="0.07" />
        <rect x="13" y="13" width="71" height="104" rx="6"  fill="url(#bkBg)" />
        <rect x="13" y="13" width="71" height="104" rx="6"  fill="none" stroke={accent} strokeWidth="2"   opacity="0.85" />
        <rect x="19" y="20" width="59" height="90"  rx="4"  fill="none" stroke={accent} strokeWidth="0.8" opacity="0.28" />
        <rect x="16" y="16" width="68" height="20"  rx="5"  fill={accent} opacity="0.05" />
        <rect x="13" y="13" width="11" height="104" rx="5"  fill="url(#bkSpine)" opacity="0.80" />
        <line x1="24" y1="13" x2="24" y2="117" stroke={accent} strokeWidth="0.8" opacity="0.50" />
        <line x1="29" y1="28" x2="75" y2="28"  stroke={accent} strokeWidth="0.9" opacity="0.40" />
        <line x1="29" y1="102" x2="75" y2="102" stroke={accent} strokeWidth="0.9" opacity="0.40" />
        <circle cx="50" cy="65" r="20" fill="none" stroke={accent} strokeWidth="1.4" opacity="0.50" />
        <circle cx="50" cy="65" r="12" fill={accent} opacity="0.07" />
        <line x1="50" y1="45" x2="50" y2="85" stroke={accent} strokeWidth="1.4" opacity="0.48" />
        <line x1="30" y1="65" x2="70" y2="65" stroke={accent} strokeWidth="1.4" opacity="0.48" />
        <line x1="36" y1="51" x2="64" y2="79" stroke={accent} strokeWidth="0.9" opacity="0.28" />
        <line x1="64" y1="51" x2="36" y2="79" stroke={accent} strokeWidth="0.9" opacity="0.28" />
        <circle cx="50" cy="45" r="2.5" fill={accent} opacity="0.70" />
        <circle cx="50" cy="85" r="2.5" fill={accent} opacity="0.70" />
        <circle cx="30" cy="65" r="2.5" fill={accent} opacity="0.70" />
        <circle cx="70" cy="65" r="2.5" fill={accent} opacity="0.70" />
        {isError && <rect x="13" y="13" width="71" height="104" rx="6" fill="#ef4444" opacity="0.06" />}
      </g>

      {isSuccess && (
        <circle cx="50" cy="65" r="50" fill="none" stroke={accent} strokeWidth="1.5"
                strokeDasharray="314" opacity="0.35"
                style={{ animation:"bkRing 1.5s 0.3s ease-out forwards", transformOrigin:"50px 65px" }} />
      )}
    </svg>
  );
}

// ─── Book animation scene (login view) ───────────────────────────────────────
function BookAnimation({ state }) {
  ensureStyles();
  const isSuccess = state === "success";
  const isError   = state === "error";
  const isLoading = state === "loading";

  const labelText  = isError   ? "Zugang verweigert"
                   : isSuccess ? "Willkommen!"
                   : isLoading ? "Wird geprüft…"
                   :             "Bookspace";
  const labelColor = isError ? "#ef4444" : isSuccess ? "#c084fc" : isLoading ? "#f59e0b" : "#38bdf8";

  const sparks = isSuccess ? [
    { angle:  0, dist:44, size: 6, color:"#fbbf24", delay:0.10, shape:"circle"  },
    { angle: 45, dist:50, size: 5, color:"#a855f7", delay:0.13, shape:"circle"  },
    { angle: 90, dist:46, size: 7, color:"#38bdf8", delay:0.08, shape:"circle"  },
    { angle:135, dist:48, size: 5, color:"#fbbf24", delay:0.15, shape:"circle"  },
    { angle:180, dist:45, size: 6, color:"#a855f7", delay:0.12, shape:"circle"  },
    { angle:225, dist:49, size: 5, color:"#38bdf8", delay:0.11, shape:"circle"  },
    { angle:270, dist:47, size: 7, color:"#fbbf24", delay:0.09, shape:"circle"  },
    { angle:315, dist:50, size: 5, color:"#a855f7", delay:0.14, shape:"circle"  },
    { angle: 22, dist:70, size:14, color:"#fbbf24", delay:0.18, shape:"star"    },
    { angle: 67, dist:74, size:12, color:"#c084fc", delay:0.22, shape:"star"    },
    { angle:112, dist:67, size:16, color:"#38bdf8", delay:0.16, shape:"star"    },
    { angle:157, dist:72, size:13, color:"#fbbf24", delay:0.24, shape:"star"    },
    { angle:202, dist:70, size:15, color:"#c084fc", delay:0.20, shape:"star"    },
    { angle:247, dist:74, size:12, color:"#38bdf8", delay:0.19, shape:"star"    },
    { angle:292, dist:68, size:14, color:"#fbbf24", delay:0.23, shape:"star"    },
    { angle:337, dist:72, size:13, color:"#c084fc", delay:0.21, shape:"star"    },
    { angle: 10, dist:94, size:16, color:"#fbbf24", delay:0.30, shape:"diamond" },
    { angle: 80, dist:90, size:14, color:"#a855f7", delay:0.34, shape:"diamond" },
    { angle:150, dist:96, size:16, color:"#38bdf8", delay:0.28, shape:"diamond" },
    { angle:220, dist:92, size:15, color:"#fbbf24", delay:0.36, shape:"diamond" },
    { angle:290, dist:88, size:13, color:"#a855f7", delay:0.32, shape:"diamond" },
  ] : [];

  return (
    <div className="bk-wrap">
      <div className="bk-scene">
        {isLoading && <>
          <OrbitDot delay={0}    color="#f59e0b" />
          <OrbitDot delay={0.47} color="#fbbf24" />
          <OrbitDot delay={0.93} color="#f97316" />
        </>}
        <BookSVG state={state} />
        {sparks.map((s, i) => <Spark key={i} {...s} />)}
      </div>
      <span className="bk-label" style={{ color: labelColor }}>{labelText}</span>
    </div>
  );
}

// ─── Open-book registration form ─────────────────────────────────────────────
function OpenBookRegister({ animState, error, disabled, onSubmit, onBack }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");

  const isLoading = animState === "loading";
  const isError   = animState === "error";
  const isSuccess = animState === "success";

  const accent = isError ? "#ef4444" : isLoading ? "#f59e0b" : isSuccess ? "#a855f7" : "#38bdf8";

  const bookAnim = isLoading ? "bkLoadGlow 0.9s ease-in-out infinite"
    : isError   ? "bkShake 0.80s ease-out, bkErrorGlow 0.80s ease-out"
    : isSuccess ? "bkSuccessGlow 2s ease-in-out infinite"
    :             "bkBookOpenIn 0.55s cubic-bezier(.2,1.1,.5,1) both";

  const inputCls = `bk-page-input${isError ? " err" : ""}`;

  // Shared input style (color adapts to accent)
  const iStyle = { "--bk-focus": accent };

  const pageRule = { borderTop: `1px solid ${accent}22`, margin: "8px 0" };
  const dotLines = (n) => Array.from({ length: n }, (_, i) => <div key={i} style={pageRule} />);

  return (
    <div style={{ animation: "bkFormIn 0.45s ease-out both" }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 14 }}>
        <span style={{ color: accent, fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.18em", textTransform: "uppercase", transition: "color .4s" }}>
          ✦ Konto erstellen ✦
        </span>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); onSubmit({ username, password, confirm }); }}>
        {/* The open book */}
        <div style={{
          display: "flex",
          background: "linear-gradient(135deg, #070f1c, #030810)",
          border: `2px solid ${accent}`,
          borderRadius: 8,
          overflow: "hidden",
          boxShadow: `0 0 28px ${accent}30`,
          animation: bookAnim,
          transition: "border-color .4s, box-shadow .4s",
        }}>

          {/* ── Left page: Username ── */}
          <div style={{ flex: 1, padding: "16px 14px 14px 18px", borderRight: `1px solid ${accent}28`, display: "flex", flexDirection: "column" }}>
            <div style={{ textAlign: "center", color: accent, fontSize: "0.58rem", letterSpacing: "0.2em", opacity: 0.50, marginBottom: 8 }}>— I —</div>
            {dotLines(1)}

            <div style={{ flex: 1 }}>
              <label className="bk-page-label" style={{ color: accent }}>Benutzername</label>
              <input
                className={inputCls}
                style={{ ...iStyle, borderColor: `${accent}55` }}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
                minLength={3}
                disabled={disabled || isLoading || isSuccess}
                placeholder="min. 3 Zeichen"
              />
            </div>

            <div style={{ marginTop: "auto", paddingTop: 10 }}>{dotLines(3)}</div>
          </div>

          {/* ── Right page: Passwords ── */}
          <div style={{ flex: 1, padding: "16px 18px 14px 14px", display: "flex", flexDirection: "column" }}>
            <div style={{ textAlign: "center", color: accent, fontSize: "0.58rem", letterSpacing: "0.2em", opacity: 0.50, marginBottom: 8 }}>— II —</div>
            {dotLines(1)}

            <div style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>
              <div>
                <label className="bk-page-label" style={{ color: accent }}>Passwort</label>
                <input
                  type="password"
                  className={inputCls}
                  style={{ ...iStyle, borderColor: `${accent}55` }}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  disabled={disabled || isLoading || isSuccess}
                  placeholder="min. 8 Zeichen"
                />
              </div>
              <div>
                <label className="bk-page-label" style={{ color: accent }}>Bestätigen</label>
                <input
                  type="password"
                  className={`${inputCls}${confirm && confirm !== password ? " err" : ""}`}
                  style={{ ...iStyle, borderColor: confirm && confirm !== password ? "#ef444488" : `${accent}55` }}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  minLength={8}
                  disabled={disabled || isLoading || isSuccess}
                  placeholder="Passwort wiederholen"
                />
              </div>
            </div>

            <div style={{ marginTop: "auto", paddingTop: 10 }}>{dotLines(2)}</div>
          </div>
        </div>

        {/* Error / success messages */}
        {error && !isSuccess && (
          <div className="alert alert-error" style={{ marginTop: 12 }}>{error}</div>
        )}
        {isSuccess && (
          <div style={{ textAlign: "center", marginTop: 12, color: "#c084fc", animation: "bkFormIn 0.4s ease-out both" }}>
            ✦ Konto erstellt — weiter zum Login…
          </div>
        )}

        {/* Submit */}
        {!isSuccess && (
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isLoading || disabled || (!!confirm && confirm !== password)}
            style={{ width: "100%", justifyContent: "center", marginTop: 14 }}
          >
            {isLoading ? "Wird erstellt…" : "Registrieren"}
          </button>
        )}
      </form>

      {!isSuccess && (
        <div className="auth-switch" style={{ marginTop: 12 }}>
          <button className="link-btn" onClick={onBack} disabled={isLoading}>
            ← Zurück zum Login
          </button>
        </div>
      )}
    </div>
  );
}

// ─── LoginForm ────────────────────────────────────────────────────────────────
// Props:
//   onLogin(credentials)        → Promise<userData>  (API call, does NOT navigate)
//   onLoginComplete(userData)   → void               (triggers navigation in parent)
//   onRegister(credentials)     → Promise<void>      (API call)
const LoginForm = ({ onLogin, onLoginComplete, onRegister }) => {
  const [view,          setView]          = useState("login");
  const [animState,     setAnimState]     = useState("idle");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [error,         setError]         = useState(null);
  const [loading,       setLoading]       = useState(false);
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  // ── Login submit ────────────────────────────────────────────────────────────
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    clearTimeout(timerRef.current);
    setLoading(true); setError(null); setAnimState("loading");
    try {
      const user = await onLogin({ username: loginUsername, password: loginPassword });
      setAnimState("success");
      // Delay navigation so the full animation plays (cover opens + sparks burst)
      timerRef.current = setTimeout(() => onLoginComplete(user), 2000);
    } catch (err) {
      setAnimState("error");
      setError(err.response?.data?.detail || "Falsches Passwort oder Benutzername.");
      timerRef.current = setTimeout(() => { setAnimState("idle"); setError(null); }, 2200);
    } finally {
      setLoading(false);
    }
  };

  // ── Switch to register: book cover opens, then form unfolds ────────────────
  const handleRegisterClick = () => {
    if (loading) return;
    clearTimeout(timerRef.current);
    setError(null);
    setAnimState("opening");
    timerRef.current = setTimeout(() => {
      setView("register");
      setAnimState("idle");
    }, 680);
  };

  // ── Back to login (optionally pre-fills username) ──────────────────────────
  const handleBackToLogin = (prefilledUsername = "") => {
    clearTimeout(timerRef.current);
    setView("login");
    setAnimState("idle");
    setError(null);
    if (prefilledUsername) setLoginUsername(prefilledUsername);
  };

  // ── Register submit ─────────────────────────────────────────────────────────
  const handleRegisterSubmit = async ({ username, password, confirm }) => {
    if (loading) return;
    if (password !== confirm) { setError("Passwörter stimmen nicht überein."); return; }
    clearTimeout(timerRef.current);
    setLoading(true); setError(null); setAnimState("loading");
    try {
      await onRegister({ username, password });
      setAnimState("success");
      timerRef.current = setTimeout(() => handleBackToLogin(username), 1800);
    } catch (err) {
      setAnimState("error");
      setError(err.response?.data?.detail || "Registrierung fehlgeschlagen.");
      timerRef.current = setTimeout(() => setAnimState("idle"), 2200);
    } finally {
      setLoading(false);
    }
  };

  const isLoginSuccess  = view === "login"    && animState === "success";
  const isLoginOpening  = view === "login"    && animState === "opening";

  return (
    <div className="auth-panel">

      {/* ══ LOGIN VIEW ══════════════════════════════════════════════════════ */}
      {view === "login" && (
        <>
          <BookAnimation state={animState} />

          {/* Login form — hidden during opening transition and after success */}
          {!isLoginSuccess && (
            <div
              className="bk-form-in"
              style={isLoginOpening
                ? { animation: "bkFadeOut 0.38s ease-out forwards", pointerEvents: "none" }
                : undefined}
            >
              <h2 style={{ marginBottom: 4 }}>Willkommen zurück</h2>
              <p className="auth-sub" style={{ marginBottom: 20 }}>Melde dich in deiner Bibliothek an</p>

              {error && (
                <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>
              )}

              <form onSubmit={handleLoginSubmit}>
                <div className="field">
                  <label>Benutzername</label>
                  <input value={loginUsername} onChange={(e) => setLoginUsername(e.target.value)} autoFocus required disabled={loading} />
                </div>
                <div className="field">
                  <label>Passwort</label>
                  <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} required disabled={loading} />
                </div>
                <button className="btn btn-primary" type="submit" disabled={loading}
                        style={{ width: "100%", justifyContent: "center" }}>
                  {loading ? "Wird geprüft…" : "Anmelden"}
                </button>
              </form>

              <div className="auth-switch">
                Noch kein Konto?{" "}
                <button className="link-btn" onClick={handleRegisterClick} disabled={loading}>
                  Jetzt registrieren
                </button>
              </div>
            </div>
          )}

          {/* Success message visible while animation plays */}
          {isLoginSuccess && (
            <div style={{ textAlign: "center", marginTop: 8, animation: "bkFormIn 0.5s 0.6s ease-out both" }}>
              <p style={{ color: "#c084fc", fontWeight: 600, fontSize: "1.05rem" }}>
                Die Bibliothek öffnet sich ✨
              </p>
              <p style={{ color: "var(--text-2)", fontSize: "0.85rem", marginTop: 6 }}>
                Willkommen zurück…
              </p>
            </div>
          )}
        </>
      )}

      {/* ══ REGISTER VIEW ═══════════════════════════════════════════════════ */}
      {view === "register" && (
        <OpenBookRegister
          animState={animState}
          error={error}
          disabled={loading}
          onSubmit={handleRegisterSubmit}
          onBack={handleBackToLogin}
        />
      )}
    </div>
  );
};

export default LoginForm;
