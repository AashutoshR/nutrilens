import { useEffect, useState } from "react";
import { api } from "../api.js";
import { MEAL_EMOJI, cuisineEmoji, greeting } from "../theme.js";
import { ErrorNote, GapCard, Icon, MacroDonut, NutrientRings, SectionHeader, Spinner, fmt } from "./ui.jsx";

export default function TodayPage({ profile, onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = () => api.today().then(setData).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function remove(id) {
    await api.deleteMeal(id).catch((e) => setError(e.message));
    load();
  }

  if (error) return <div className="page page-wide"><ErrorNote message={error} onRetry={load} /></div>;
  if (!data) return <div className="page page-wide"><Spinner label="Loading your day…" /></div>;

  const { meals, evaluation: ev, history } = data;
  const firstName = profile.name.trim().split(" ")[0];

  return (
    <div className="page page-wide">
      <header className="page-head">
        <span className="eyebrow">{new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</span>
        <h1 className="display page-title">{greeting()}{firstName ? `, ${firstName}` : ""} <span className="wave">👋</span></h1>
        <p className="lead">{meals.length ? "Here's how your day is shaping up." : "Your day is a blank plate. Let's fill it well."}</p>
      </header>

      {meals.length === 0 ? (
        <section className="empty-state">
          <div className="empty-plate" aria-hidden="true"><span>🍽️</span></div>
          <h2 className="display">No meals logged yet</h2>
          <p className="muted">Scan your first meal to start filling your rings and get suggestions for the rest of the day.</p>
          <button className="btn btn-primary btn-lg" onClick={() => onNavigate("scan")}><Icon name="camera" /> Scan a meal</button>
        </section>
      ) : (
        <>
          <section className="today-hero">
            <ActivityRings ev={ev} />
            <div className="today-stats">
              <Stat emoji="🔥" label="Eaten" value={fmt(ev.totals.calories)} unit="kcal" tone="tomato" />
              <Stat emoji="🎯" label="Remaining" value={fmt(Math.max(0, ev.targets.calories - ev.totals.calories))} unit="kcal" tone="leaf" />
              <Stat emoji="🍽️" label="Meals" value={meals.length} unit="logged" tone="saffron" />
              <Stat emoji="⚠️" label="Allergen hits" value={ev.allergen_conflicts.length} unit={ev.allergen_conflicts.length ? ev.allergen_conflicts.join(", ") : "none today"} tone={ev.allergen_conflicts.length ? "danger" : "sky"} />
            </div>
          </section>

          <div className="bento">
            <section className="card card-pad span-7">
              <div className="card-head">
                <span className="card-icon tone-leaf"><Icon name="clock" size={18} /></span>
                <div><h3>Today's meals</h3><small>{meals.length} logged</small></div>
              </div>
              <ol className="timeline">
                {meals.map((m) => (
                  <li key={m.id}>
                    <span className="tl-time">{new Date(m.eaten_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
                    <span className="tl-dot" />
                    <div className="tl-card">
                      {m.thumbnail ? <img src={m.thumbnail} alt="" /> : <span className="tl-thumb">{cuisineEmoji(m.cuisine)}</span>}
                      <div className="tl-info">
                        <strong>{m.dish_name}</strong>
                        <small>{MEAL_EMOJI[m.meal_type] || "🍽️"} <span className="cap">{m.meal_type}</span>{m.cuisine && ` · ${m.cuisine}`}</small>
                      </div>
                      <span className="tl-kcal">{fmt(m.calories)}<small> kcal</small></span>
                      <button className="icon-btn" aria-label={`Delete ${m.dish_name}`} onClick={() => remove(m.id)}><Icon name="trash" size={15} /></button>
                    </div>
                  </li>
                ))}
              </ol>
              <button className="btn btn-outline btn-sm add-meal" onClick={() => onNavigate("scan")}><Icon name="camera" size={16} /> Add a meal</button>
            </section>

            <section className="card card-pad span-5">
              <div className="card-head">
                <span className="card-icon tone-saffron">🥧</span>
                <div><h3>Macros so far</h3><small>Bars show progress to your daily targets</small></div>
              </div>
              <MacroDonut split={ev.macro_split} calories={ev.totals.calories} totals={ev.totals} targets={ev.targets} />
            </section>

            <section className="card card-pad span-12">
              <div className="card-head">
                <span className="card-icon tone-plum">🧪</span>
                <div><h3>Vitamins & minerals</h3><small>Progress towards today's targets</small></div>
              </div>
              <NutrientRings nutrients={ev.nutrients} scope="day" />
            </section>
          </div>

          {ev.gaps.length > 0 && (
            <section className="stack">
              <SectionHeader eyebrow="For the rest of today" title="Still on your plate to get" />
              <div className="gap-grid">
                {ev.gaps.map((g) => (
                  <GapCard key={g.nutrient} gap={g} scope="day" onFindRecipes={(n) => onNavigate("recipes", { focus_nutrient: n })} />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {history.length > 1 && <History history={history} target={ev.targets.calories} />}
    </div>
  );
}

function Stat({ emoji, label, value, unit, tone }) {
  return (
    <div className={`stat tone-${tone}`}>
      <span className="stat-emoji" aria-hidden="true">{emoji}</span>
      <small>{label}</small>
      <strong>{value}</strong>
      <span>{unit}</span>
    </div>
  );
}

function ActivityRings({ ev }) {
  const rings = [
    { label: "Calories", color: "var(--tomato)", value: ev.totals.calories, target: ev.targets.calories, unit: "kcal" },
    { label: "Protein", color: "var(--protein)", value: ev.totals.protein_g, target: ev.targets.protein_g, unit: "g" },
    { label: "Fiber", color: "var(--leaf)", value: ev.totals.fiber_g, target: ev.targets.fiber_g, unit: "g" },
  ];
  const size = 200;
  return (
    <div className="activity">
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className="activity-svg" role="img"
        aria-label={rings.map((r) => `${r.label} ${Math.round((100 * r.value) / r.target)}%`).join(", ")}>
        {rings.map((r, i) => {
          const radius = 86 - i * 24;
          const c = 2 * Math.PI * radius;
          const pct = Math.min(1, r.value / r.target);
          return (
            <g key={r.label}>
              <circle cx="100" cy="100" r={radius} fill="none" stroke={r.color} strokeOpacity="0.16" strokeWidth="18" />
              <circle className="ring-progress" cx="100" cy="100" r={radius} fill="none" stroke={r.color} strokeWidth="18"
                strokeLinecap="round" strokeDasharray={`${pct * c} ${c}`} transform="rotate(-90 100 100)" />
            </g>
          );
        })}
      </svg>
      <ul className="activity-legend">
        {rings.map((r) => (
          <li key={r.label}>
            <span className="dot" style={{ background: r.color }} />
            <div>
              <small>{r.label}</small>
              <strong>{fmt(r.value)}<span>/{fmt(r.target)} {r.unit}</span></strong>
            </div>
            <em>{Math.round((100 * r.value) / r.target)}%</em>
          </li>
        ))}
      </ul>
    </div>
  );
}

function History({ history, target }) {
  const days = [...history].reverse();
  const max = Math.max(target, ...days.map((d) => d.calories)) * 1.15;
  return (
    <section className="card card-pad">
      <div className="card-head">
        <span className="card-icon tone-sky"><Icon name="today" size={18} /></span>
        <div><h3>Your week</h3><small>Calories per day vs your target</small></div>
      </div>
      <div className="history-chart">
        <div className="history-target" style={{ bottom: `${(target / max) * 100}%` }}><span>Target {fmt(target)}</span></div>
        {days.map((d) => (
          <div key={d.day} className="history-col" title={`${d.calories} kcal · ${d.meals} meals`}>
            <div className={`history-bar ${d.calories > target ? "over" : ""}`} style={{ height: `${(d.calories / max) * 100}%` }}>
              <span>{fmt(d.calories)}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="history-days">
        {days.map((d) => <small key={d.day}>{new Date(d.day + "T12:00").toLocaleDateString(undefined, { weekday: "short" })}</small>)}
      </div>
    </section>
  );
}
