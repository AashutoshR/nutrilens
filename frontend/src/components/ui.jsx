import { useEffect, useRef } from "react";
import { NUTRIENT_EMOJI, cuisineEmoji } from "../theme.js";

const PATHS = {
  scan: "M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2M9 12a3 3 0 1 0 6 0 3 3 0 0 0-6 0",
  today: "M4 19V9M10 19V5M16 19v-7M22 19H2",
  leaf: "M5 19c0-8 5-14 15-15-1 10-7 15-15 15zM5 19l7-7",
  recipe: "M6 3v8a3 3 0 0 0 6 0V3M9 3v18M17 3c-2 2-2 6 0 8v10",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c1-4 4-6 8-6s7 2 8 6",
  camera: "M4 8h3l2-3h6l2 3h3v11H4zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  alert: "M12 3l10 18H2zM12 10v5M12 18h.01",
  check: "M5 12l5 5 9-10",
  x: "M6 6l12 12M18 6L6 18",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  sparkle: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  arrow: "M5 12h14M13 6l6 6-6 6",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  undo: "M9 14L4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3",
  chevron: "M9 6l6 6-6 6",
};

/**
 * Ref for a sticky side panel that may be taller than the window. Short panels stick near the top;
 * tall ones scroll with the page until their bottom is in view and then stick, so nothing is ever cut off.
 */
export function useFitSticky(gap = 24) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const scroller = el.closest(".main-area");
    const fit = () => {
      const view = scroller ? scroller.clientHeight : window.innerHeight;
      el.style.top = `${Math.min(gap, view - el.offsetHeight - gap)}px`;
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    if (scroller) observer.observe(scroller);
    window.addEventListener("resize", fit);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", fit);
    };
  }, [gap]);
  return ref;
}

export function Icon({ name, size = 20, className = "" }) {
  return (
    <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

export function Logo({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="16" style={{ fill: "var(--ink)" }} />
      <circle cx="29" cy="29" r="13" fill="none" style={{ stroke: "var(--bg)" }} strokeWidth="5" />
      <path d="M39 39l9 9" style={{ stroke: "var(--bg)" }} strokeWidth="6" strokeLinecap="round" />
      <path d="M23 32c0-7 5-11 12-11-1 7-5 11-12 11z" style={{ fill: "var(--leaf)" }} />
    </svg>
  );
}

export function Spinner({ label }) {
  return (
    <div className="spinner-wrap" role="status">
      <span className="spinner" />
      {label && <span>{label}</span>}
    </div>
  );
}

export function ErrorNote({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="alert alert-error" role="alert">
      <span className="alert-icon"><Icon name="alert" size={18} /></span>
      <span>{message}</span>
      {onRetry && <button className="btn btn-ghost btn-sm" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function SectionHeader({ eyebrow, title, children }) {
  return (
    <header className="section-header">
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h2 className="display">{title}</h2>
      {children && <p>{children}</p>}
    </header>
  );
}

/** A single progress ring; `pct` may exceed 100 (the ring just closes). */
export function Ring({ pct, size = 64, stroke = 7, color = "var(--leaf)", children, track = "var(--track)" }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const len = (Math.min(Math.max(pct, 0), 100) / 100) * c;
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
        <circle className="ring-progress" cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={`${len} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="ring-center">{children}</div>
    </div>
  );
}

/** Health score as a number plus a 10-step bar: easy to read at a glance, nothing to overlap. */
export function HealthScore({ score, summary }) {
  const tone = score >= 7 ? "good" : score >= 4 ? "fair" : "poor";
  const verdict = score >= 8 ? "Excellent" : score >= 6 ? "Good" : score >= 4 ? "Fair" : "Treat";
  return (
    <section className={`health-score tone-${tone}`} aria-label={`Health score ${score} out of 10, ${verdict}`}>
      <div className="hs-top">
        <span className="hs-label">Health score</span>
        <span className="hs-verdict">{verdict}</span>
      </div>
      <div className="hs-value"><strong>{score}</strong><span>/ 10</span></div>
      <div className="hs-bar" aria-hidden="true">
        {Array.from({ length: 10 }, (_, i) => <i key={i} className={i < score ? "on" : ""} />)}
      </div>
      {summary && <p className="hs-summary">{summary}</p>}
    </section>
  );
}

const MACROS = [
  { key: "protein", grams: "protein_g", label: "Protein", color: "var(--protein)" },
  { key: "carbs", grams: "carbs_g", label: "Carbs", color: "var(--carbs)" },
  { key: "fat", grams: "fat_g", label: "Fat", color: "var(--fat)" },
];

export function MacroDonut({ split, calories, totals, targets }) {
  const r = 46;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="macro">
      <div className="donut">
        <svg viewBox="0 0 120 120" width="164" height="164">
          <circle cx="60" cy="60" r={r} fill="none" stroke="var(--track)" strokeWidth="16" />
          {MACROS.map((m) => {
            const len = (split[m.key] / 100) * c;
            const seg = (
              <circle key={m.key} className="ring-progress" cx="60" cy="60" r={r} fill="none" stroke={m.color} strokeWidth="16"
                strokeDasharray={`${Math.max(len - 2, 0)} ${c}`} strokeDashoffset={-offset} transform="rotate(-90 60 60)" />
            );
            offset += len;
            return seg;
          })}
        </svg>
        <div className="ring-center donut-value">
          <strong>{Math.round(calories)}</strong>
          <small>kcal</small>
        </div>
      </div>
      <ul className="macro-legend">
        {MACROS.map((m) => {
          const grams = totals[m.grams];
          const pct = targets ? Math.min(100, (100 * grams) / targets[m.grams]) : split[m.key];
          return (
            <li key={m.key}>
              <div className="macro-row">
                <span><span className="dot" style={{ background: m.color }} />{m.label}</span>
                <strong>{Math.round(grams)} g <small>{split[m.key]}%</small></strong>
              </div>
              <div className="meter"><span style={{ width: `${pct}%`, background: m.color }} /></div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const MICROS = ["iron_mg", "calcium_mg", "vitamin_c_mg", "vitamin_d_mcg", "vitamin_b12_mcg", "fiber_g",
  "potassium_mg", "magnesium_mg", "zinc_mg", "folate_mcg", "sodium_mg", "sugar_g"];

const STATUS_COLOR = { good: "var(--leaf)", low: "var(--saffron)", high: "var(--tomato)", ok: "var(--sky)" };

export function NutrientRings({ nutrients, scope = "meal" }) {
  const rows = MICROS.map((k) => nutrients.find((n) => n.key === k)).filter(Boolean);
  return (
    <>
      <div className="nutrient-rings">
        {rows.map((n, i) => (
          <div key={n.key} className={`nutrient-ring status-${n.status}`} style={{ "--i": i }}
            title={`${n.label}: ${fmt(n.amount)} ${n.unit} of ${fmt(n.daily_target)} ${n.unit} daily${n.kind === "limit" ? " limit" : ""}`}>
            <Ring pct={n.pct_daily} size={66} stroke={6} color={STATUS_COLOR[n.status]}>
              <span className="ring-emoji" aria-hidden="true">{NUTRIENT_EMOJI[n.key]}</span>
            </Ring>
            <strong>{n.label.replace("Vitamin ", "Vit ")}</strong>
            <small>{fmt(n.amount)} {n.unit}</small>
            <span className="pct">{n.pct_daily}%{n.kind === "limit" ? " of limit" : ""}</span>
          </div>
        ))}
      </div>
      <div className="legend-row">
        <span><i style={{ background: "var(--leaf)" }} /> On track</span>
        <span><i style={{ background: "var(--saffron)" }} /> Running low</span>
        <span><i style={{ background: "var(--sky)" }} /> Within limit</span>
        <span><i style={{ background: "var(--tomato)" }} /> Over the limit</span>
        <span className="muted">{scope === "meal" ? "% of your daily target · one meal ≈ 33%" : "% of your daily target so far"}</span>
      </div>
    </>
  );
}

export function fmt(n) {
  if (n >= 100) return Math.round(n).toLocaleString();
  if (n >= 10) return n.toFixed(0);
  return n.toFixed(1).replace(/\.0$/, "");
}

export function AllergenPanel({ allergens, hidden = [], avoid = [] }) {
  const conflicts = allergens.filter((a) => a.conflict);
  // Free-text "may contain" warnings that mention one of the user's allergens get flagged too.
  const mentionsAvoided = (text) => avoid.some((a) => text.toLowerCase().includes(a.replace("_", " ").replace(/s$/, "")));
  return (
    <section className="card card-pad">
      <div className="card-head">
        <span className="card-icon tone-tomato"><Icon name="shield" size={18} /></span>
        <div><h3>Allergen radar</h3><small>{allergens.length ? `${allergens.length} detected` : "All clear"}</small></div>
      </div>
      {conflicts.length > 0 && (
        <div className="alert alert-danger" role="alert">
          <span className="alert-icon"><Icon name="alert" size={18} /></span>
          <span><strong>Contains {conflicts.map((a) => a.label).join(", ")}</strong>, which is on your avoid list.</span>
        </div>
      )}
      {allergens.length === 0 ? (
        <div className="all-clear"><span aria-hidden="true">🛡️</span><p>No major allergens detected in what we can see.</p></div>
      ) : (
        <div className="allergen-grid">
          {allergens.map((a) => (
            <div key={a.key} className={`allergen ${a.conflict ? "conflict" : ""}`}>
              <span className="allergen-icon" aria-hidden="true">{a.icon}</span>
              <div><strong>{a.label}</strong><small>{a.items.join(", ")}</small></div>
            </div>
          ))}
        </div>
      )}
      {hidden.length > 0 && (
        <ul className="hidden-list">
          {hidden.map((h, i) => (
            <li key={i} className={mentionsAvoided(h) ? "risk" : ""}>
              <span aria-hidden="true">{mentionsAvoided(h) ? "⚠️" : "🔍"}</span>
              <span>{mentionsAvoided(h) && <strong>May contain something you avoid: </strong>}{h}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="fine-print">Photos can't reveal every ingredient. With a severe allergy, always check with whoever made the food.</p>
    </section>
  );
}

export function GapCard({ gap, onFindRecipes, scope = "meal", guide = false }) {
  const label = gap.label.startsWith("Vitamin") ? gap.label : gap.label.toLowerCase();
  const maxAmount = Math.max(...gap.sources.map((s) => s.amount), 1);
  const pct = gap.pct_daily ?? 0;
  return (
    <article className={`gap-card ${guide ? "gap-guide" : ""}`}>
      <header className="gap-head">
        <span className="gap-emoji" aria-hidden="true">{NUTRIENT_EMOJI[gap.nutrient]}</span>
        <div className="gap-title">
          <span className="eyebrow">{guide ? "Nutrient guide" : scope === "meal" ? "Running low in this meal" : "Still needed today"}</span>
          <h3 className="display">{guide ? gap.label : `Low in ${gap.label}`}</h3>
          {!guide && (
            <>
              <div className="meter meter-lg"><span style={{ width: `${Math.min(pct, 100)}%` }} /></div>
              <small>{fmt(gap.amount)} of {fmt(gap.daily_target)} {gap.unit} daily target · {pct}%</small>
            </>
          )}
        </div>
      </header>

      <p className="gap-why">{gap.why}</p>
      {guide && gap.deficiency_signs && (
        <div className="signs">
          <span className="signs-label">Signs you might be low</span>
          <div className="chips">{gap.deficiency_signs.map((s) => <span key={s} className="chip chip-soft">{s}</span>)}</div>
        </div>
      )}

      <div className="gap-body">
        <div>
          <h4>Best sources for you</h4>
          <ul className="sources">
            {gap.sources.map((s) => (
              <li key={s.name}>
                <div className="source-top">
                  <span>{s.name}</span>
                  <strong>{fmt(s.amount)} {gap.unit}</strong>
                </div>
                <div className="meter"><span style={{ width: `${(s.amount / maxAmount) * 100}%` }} /></div>
                <small>per {s.serving}</small>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4>Popular dishes to try</h4>
          <div className="dishes">
            {gap.dishes.map((d) => (
              <div key={d.name + d.cuisine} className={`dish ${d.preferred ? "preferred" : ""}`}>
                <span className="dish-emoji" aria-hidden="true">{cuisineEmoji(d.cuisine)}</span>
                <div>
                  <strong>{d.name}</strong>
                  <small>{d.blurb}</small>
                  <span className="dish-cuisine">
                    {d.cuisine}{d.preferred && <> · <Icon name="star" size={11} /> Your cuisine</>}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="tip"><span aria-hidden="true">💡</span><p>{gap.tip}</p></div>
      <footer className="gap-foot">
        {gap.filtered_out > 0 && <small className="muted">{gap.filtered_out} options hidden to match your diet & allergens</small>}
        {onFindRecipes && (
          <button className="btn btn-dark btn-sm" onClick={() => onFindRecipes(gap.nutrient)}>
            Cook something {label}-rich <Icon name="arrow" size={16} />
          </button>
        )}
      </footer>
    </article>
  );
}
