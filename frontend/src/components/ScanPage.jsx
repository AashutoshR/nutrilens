import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { prepareImage } from "../image.js";
import { MEAL_EMOJI, cuisineEmoji, gradientFor } from "../theme.js";
import { AllergenPanel, ErrorNote, GapCard, Icon, MacroDonut, NutrientRings, HealthScore, SectionHeader, fmt, useFitSticky } from "./ui.jsx";
import Webcam from "./Webcam.jsx";

// The real stages of an analysis job (see backend/app/analysis.py).
const STAGES = [
  { key: "looking", emoji: "🔍", label: "AI is spotting each food" },
  { key: "matching", emoji: "📚", label: "Matching foods to the USDA nutrition database" },
  { key: "done", emoji: "🧮", label: "Calculating nutrients, allergens and tips" },
];

// Illustration used for built-in sample meals, so a sample is never mistaken for the user's photo.
function sampleArt(emoji) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff1cc"/><stop offset="1" stop-color="#ffc9a8"/></linearGradient></defs>
    <rect width="400" height="300" fill="url(#g)"/>
    <circle cx="200" cy="150" r="110" fill="#ffffff" opacity="0.9"/><circle cx="200" cy="150" r="84" fill="#f7f2e8"/>
    <text x="200" y="188" font-size="104" text-anchor="middle">${emoji}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

const isTyping = (el) => el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/**
 * The scan itself lives in App (`scan` / `scanActions`), so an analysis keeps running while the user
 * visits other pages and the result is still here when they come back.
 */
export default function ScanPage({ profile, onNavigate, onMealLogged, aiConnected, scan, scanActions }) {
  const [dragging, setDragging] = useState(false);
  const [webcam, setWebcam] = useState(false);
  const [samples, setSamples] = useState([]);
  const [localError, setLocalError] = useState("");
  const fileInput = useRef();

  const image = scan?.image;
  const busy = scan?.status === "looking" || scan?.status === "matching" || scan?.status === "uploading";
  const result = scan?.result;
  const error = localError || scan?.error?.detail || "";

  useEffect(() => {
    if (!aiConnected) api.samples().then(setSamples).catch(() => {});
  }, [aiConnected]);

  async function pick(file) {
    if (!file) return;
    setLocalError("");
    try {
      scanActions.setImage(await prepareImage(file));
    } catch (e) {
      setLocalError(e.message || "Couldn't read that image.");
    }
  }

  async function trySample(sample) {
    setLocalError("");
    try {
      const res = await api.analyzeSample(sample.id);
      scanActions.showSample({ previewUrl: sampleArt(sample.emoji), thumbnail: null, blob: null }, res);
    } catch (e) {
      setLocalError(e.message);
    }
  }

  // Desktop conveniences: paste an image (Ctrl+V), Ctrl+O to open, Enter to analyse, Esc to start over.
  useEffect(() => {
    const onPaste = (e) => {
      if (busy || webcam) return;
      const file = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"))?.getAsFile();
      if (file) {
        e.preventDefault();
        pick(file);
      }
    };
    const onKey = (e) => {
      if (webcam || busy) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "o") {
        e.preventDefault();
        fileInput.current?.click();
      } else if (e.key === "Enter" && image && !result && aiConnected && !isTyping(e.target) && !e.target.closest?.(".lens-actions")) {
        e.preventDefault();
        scanActions.analyze();
      } else if (e.key === "Escape" && (image || result) && !isTyping(e.target) && !e.target.closest?.(".match-popover")) {
        scanActions.reset();
      }
    };
    window.addEventListener("paste", onPaste);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("paste", onPaste);
      window.removeEventListener("keydown", onKey);
    };
  });

  const fileInputEl = (
    <input ref={fileInput} type="file" accept="image/*" hidden onChange={(e) => { pick(e.target.files[0]); e.target.value = ""; }} />
  );

  if (result?.analysis.is_food && result.evaluation) {
    return (
      <div className="page page-wide">
        {fileInputEl}
        <AnalysisView scan={scan} scanActions={scanActions} profile={profile} onNavigate={onNavigate}
          onMealLogged={onMealLogged} aiConnected={aiConnected} />
      </div>
    );
  }

  const profileEmpty = !profile.diets.length && !profile.allergens.length && !profile.cuisines.length;
  const stageIndex = STAGES.findIndex((s) => s.key === scan?.status);

  return (
    <div className="page">
      {fileInputEl}
      {webcam && <Webcam onClose={() => setWebcam(false)} onCapture={(file) => { setWebcam(false); pick(file); }} />}
      <section className="scan-hero">
        <div className="hero-copy">
          <span className="eyebrow-pill"><span className="pulse-dot" /> AI nutrition · USDA data</span>
          <h1 className="display hero-title">Know what's <em>really</em> on your plate.</h1>
          <p className="lead">
            Drop in a photo of your meal. AI spots every food, and NutriLens looks each one up in the USDA nutrition
            database to count nutrients, flag allergens and tell you what to eat next.
          </p>
          <div className="hero-ctas">
            <button className="btn btn-primary btn-lg" onClick={() => fileInput.current.click()} disabled={busy}>
              <Icon name="upload" /> {image ? "Choose another photo" : "Upload a photo"}
            </button>
            <button className="btn btn-outline btn-lg" onClick={() => setWebcam(true)} disabled={busy}>
              <Icon name="camera" /> Use webcam
            </button>
          </div>
          {!aiConnected && (
            <div className="connect-banner">
              <span aria-hidden="true">ℹ️</span>
              <p><strong>Photo analysis is unavailable right now.</strong> You can still browse the nutrient guide, recipes and the sample meals below.</p>
            </div>
          )}
          <p className="input-hints key-hint">
            <span><kbd>Ctrl</kbd> <kbd>O</kbd> open a file</span>
            <span><kbd>Ctrl</kbd> <kbd>V</kbd> paste an image</span>
          </p>
          <div className="hero-stats">
            <div><strong>2M</strong><span>foods in the database</span></div>
            <div><strong>14</strong><span>allergens checked</span></div>
            <div><strong>16</strong><span>nutrients tracked</span></div>
          </div>
        </div>

        <div className="lens-wrap">
          <div
            className={`lens ${dragging ? "dragging" : ""} ${image ? "has-image" : ""} ${busy ? "scanning" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files[0]); }}
          >
            <div className="lens-inner">
              <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
              {image ? (
                <>
                  <img src={image.previewUrl} alt="Your meal" />
                  {busy && (
                    <>
                      <div className="scan-grid" />
                      <div className="scan-line" />
                    </>
                  )}
                  {!busy && !result && (
                    <div className="lens-actions">
                      <button className="btn btn-primary btn-lg" onClick={scanActions.analyze} disabled={!aiConnected} title="Analyse (Enter)">
                        <Icon name="sparkle" /> Analyse my meal <kbd className="kbd-light">Enter</kbd>
                      </button>
                      <button className="btn btn-glass" onClick={scanActions.reset} title="Remove photo (Esc)"><Icon name="x" size={16} /> Remove</button>
                    </div>
                  )}
                </>
              ) : (
                <button className="lens-empty" onClick={() => fileInput.current.click()}>
                  <span className="lens-icon">{dragging ? "📥" : "🖼️"}</span>
                  <strong>{dragging ? "Drop it!" : "Drop a food photo here"}</strong>
                  <span>or click to browse your computer</span>
                </button>
              )}
            </div>
          </div>
          {busy && (
            <div className="scan-progress" aria-live="polite">
              <ol className="scan-steps">
                {STAGES.map((s, i) => (
                  <li key={s.key} className={i < stageIndex ? "done" : i === stageIndex ? "active" : ""}>
                    <span className="step-dot">{i < stageIndex ? <Icon name="check" size={14} /> : s.emoji}</span>
                    {s.label}
                  </li>
                ))}
              </ol>
              {scan.itemsSeen?.length > 0 && (
                <div className="seen-items">
                  <small>Found so far</small>
                  <div className="chips">{scan.itemsSeen.map((n) => <span key={n} className="chip chip-soft">{n}</span>)}</div>
                </div>
              )}
              <p className="progress-foot">
                <span className="timer">{clock(scan.elapsed || 0)}</span>
                Feel free to use the rest of NutriLens. We'll let you know when your meal is ready.
              </p>
            </div>
          )}
        </div>
      </section>

      <ErrorNote message={error} onRetry={image && !busy && aiConnected && image.blob ? scanActions.analyze : null} />

      {result && !result.analysis.is_food && (
        <section className="card card-pad not-food">
          <span aria-hidden="true">🤔</span>
          <div>
            <h3>That doesn't look like food</h3>
            <p className="muted">{result.analysis.health_summary}</p>
          </div>
          <button className="btn btn-primary" onClick={scanActions.reset}>Try another photo</button>
        </section>
      )}

      {!aiConnected && !image && samples.length > 0 && (
        <section className="sample-strip">
          <div>
            <h3>See an example</h3>
            <p className="muted">Built-in sample meals, clearly marked as samples. They don't analyse your photo.</p>
          </div>
          <div className="sample-buttons">
            {samples.map((s) => (
              <button key={s.id} className="sample-btn" onClick={() => trySample(s)}>
                <span aria-hidden="true">{s.emoji}</span>
                <span><strong>{s.dish_name}</strong><small>{s.cuisine} · sample</small></span>
              </button>
            ))}
          </div>
        </section>
      )}

      {profileEmpty && !image && (
        <button className="promo" onClick={() => onNavigate("profile")}>
          <span className="promo-emoji" aria-hidden="true">🎯</span>
          <span>
            <strong>Make it personal</strong>
            <small>Add your diet, allergies and favourite cuisines for tailored alerts and suggestions.</small>
          </span>
          <Icon name="arrow" />
        </button>
      )}

      {!image && (
        <>
          <section className="how">
            <SectionHeader eyebrow="How it works" title="From photo to plan" />
            <div className="how-steps">
              {[
                ["🖼️", "Add a photo", "Upload, paste or snap with your webcam: a home-cooked thali, a pizza, a cheese board."],
                ["🔍", "AI spots the food", "The AI names each food it can see and estimates the portion."],
                ["📚", "Real nutrition data", "Each food is matched to the USDA database, so nutrients and allergens come from real data, not guesses."],
              ].map(([emoji, title, text], i) => (
                <div key={title} className="how-step" style={{ "--i": i }}>
                  <span className="how-num">0{i + 1}</span>
                  <span className="how-emoji" aria-hidden="true">{emoji}</span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="features">
            <button className="feature f-allergen" onClick={() => onNavigate("profile")}>
              <span className="feature-emoji" aria-hidden="true">🛡️</span>
              <h3>Allergen radar</h3>
              <p>All 14 major allergens, including hidden ones like cashew in curry or fish sauce in dressings.</p>
            </button>
            <button className="feature f-gaps" onClick={() => onNavigate("nutrients")}>
              <span className="feature-emoji" aria-hidden="true">🥬</span>
              <h3>Fill your gaps</h3>
              <p>Low on iron? See the best sources and dishes like palak paneer or misir wot.</p>
            </button>
            <button className="feature f-recipes" onClick={() => onNavigate("recipes")}>
              <span className="feature-emoji" aria-hidden="true">👩‍🍳</span>
              <h3>Recipes & plans</h3>
              <p>Real recipes and weekly plans picked for your diet, with step-by-step cooking and a shopping list.</p>
            </button>
            <button className="feature f-today" onClick={() => onNavigate("today")}>
              <span className="feature-emoji" aria-hidden="true">📈</span>
              <h3>Daily tracking</h3>
              <p>Log meals and watch your rings fill up across the day.</p>
            </button>
          </section>
        </>
      )}
    </div>
  );
}

/** Lets the user see and change which database food an item was matched to. */
function MatchPicker({ item, onPick, onClose }) {
  const [query, setQuery] = useState(item.name);
  const [results, setResults] = useState(item.alternatives || []);
  const [loading, setLoading] = useState(false);
  const timer = useRef();
  const box = useRef();

  useEffect(() => {
    const onDoc = (e) => !box.current?.contains(e.target) && onClose();
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  function search(q) {
    setQuery(q);
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      if (q.trim().length < 2) return;
      setLoading(true);
      try {
        setResults(await api.searchFoods(q));
      } catch {
        /* keep previous results */
      } finally {
        setLoading(false);
      }
    }, 250);
  }

  return (
    <div className="match-popover" ref={box} role="dialog" aria-label={`Change the match for ${item.name}`}>
      <input autoFocus value={query} onChange={(e) => search(e.target.value)} placeholder="Search 2 million foods…" />
      <ul>
        {loading && <li className="muted small">Searching…</li>}
        {!loading && results.length === 0 && <li className="muted small">No matches. Try a simpler name.</li>}
        {results.map((r) => (
          <li key={r.fdc_id}>
            <button onClick={() => onPick(r)}>
              <strong>{r.description}</strong>
              <small>{r.source}{r.brand ? ` · ${r.brand}` : ""}{r.per_100g ? ` · ${Math.round(r.per_100g.calories)} kcal/100 g` : ""}</small>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AnalysisView({ scan, scanActions, profile, onNavigate, onMealLogged, aiConnected }) {
  const { result, image } = scan;
  const { analysis, evaluation } = result;
  const items = analysis.items;
  const [picking, setPicking] = useState(null);
  const [adding, setAdding] = useState(false);
  const asideRef = useFitSticky();
  const [error, setError] = useState("");
  const timer = useRef();

  const scaled = evaluation.items;
  const t = evaluation.totals;
  const dayPct = Math.round((100 * t.calories) / evaluation.targets.calories);
  const conflicts = evaluation.allergen_conflicts;
  const sample = result.sample;

  // Any edit re-runs the data side of the pipeline on the server (no AI involved), so it is instant.
  function recompute(nextItems) {
    scanActions.updateResult({ ...result, analysis: { ...analysis, items: nextItems } });
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const next = await api.describe({
          dish_name: analysis.dish_name, cuisine: analysis.cuisine, meal_type: analysis.meal_type, items: nextItems,
        });
        scanActions.updateResult({ ...result, analysis: { ...next.analysis, items: nextItems }, evaluation: next.evaluation });
      } catch (e) {
        setError(e.message);
      }
    }, 250);
  }

  const setItem = (index, patch) => recompute(items.map((it, i) => (i === index ? { ...it, ...patch } : it)));

  async function chooseMatch(index, food) {
    setPicking(null);
    try {
      const full = food.per_100g ? food : await api.getFood(food.fdc_id);
      const current = items[index];
      setItem(index, {
        per_100g: full.per_100g,
        match: { fdc_id: full.fdc_id, description: full.description, source: full.source },
        alternatives: [current.match, ...(current.alternatives || [])].filter((m) => m && m.fdc_id !== full.fdc_id).slice(0, 5),
      });
    } catch (e) {
      setError(e.message);
    }
  }

  async function addFood(food) {
    setAdding(false);
    try {
      const full = food.per_100g ? food : await api.getFood(food.fdc_id);
      recompute([...items, {
        name: full.description.split(",")[0], portion_description: "1 portion", estimated_grams: 100, confidence: 1,
        ingredients: [], allergens: [], per_100g: full.per_100g,
        match: { fdc_id: full.fdc_id, description: full.description, source: full.source }, alternatives: [],
      }]);
    } catch (e) {
      setError(e.message);
    }
  }

  async function logMeal() {
    try {
      await api.logMeal({
        dish_name: analysis.dish_name, cuisine: analysis.cuisine, meal_type: analysis.meal_type,
        items: items.filter((i) => i.estimated_grams > 0), thumbnail: image.thumbnail,
      });
      scanActions.updateResult({ ...result, logged: true });
      onMealLogged?.();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="results-layout">
      <aside className="results-aside" ref={asideRef}>
        <div className="aside-card">
          <div className="result-photo">
            <img src={image.previewUrl} alt={analysis.dish_name} />
            <span className="photo-badge">{MEAL_EMOJI[analysis.meal_type] || "🍽️"} <span className="cap">{analysis.meal_type}</span></span>
            {sample && <span className="sample-badge">Sample meal · not your photo</span>}
          </div>
          <div className="chips">
            <span className="chip chip-brand">{cuisineEmoji(analysis.cuisine)} {analysis.cuisine}</span>
            <span className="chip chip-soft">{items.length} foods</span>
            {analysis.data_source && <span className="chip chip-soft">USDA data</span>}
          </div>
          <h1 className="display result-title">{analysis.dish_name}</h1>
          {analysis.serving_note && <p className="serving-note">{analysis.serving_note}</p>}
          {conflicts.length > 0 && (
            <div className="alert alert-danger compact" role="alert">
              <span className="alert-icon">⚠️</span>
              <span>Contains <strong>{conflicts.join(", ")}</strong></span>
            </div>
          )}
          <HealthScore score={analysis.health_score} summary={analysis.health_summary} />
          <div className="quick-stats">
            <div className="qs qs-cal"><span>🔥</span><strong>{fmt(t.calories)}</strong><small>kcal · {dayPct}% of day</small></div>
            <div className="qs"><span className="dot" style={{ background: "var(--protein)" }} /><strong>{fmt(t.protein_g)}g</strong><small>protein</small></div>
            <div className="qs"><span className="dot" style={{ background: "var(--carbs)" }} /><strong>{fmt(t.carbs_g)}g</strong><small>carbs</small></div>
            <div className="qs"><span className="dot" style={{ background: "var(--fat)" }} /><strong>{fmt(t.fat_g)}g</strong><small>fat</small></div>
          </div>
          {sample && <p className="fine-print">This is a built-in example to show what NutriLens does. Samples can't be logged.</p>}
          <div className="aside-actions">
            {sample ? (
              <button className="btn btn-primary btn-lg" onClick={scanActions.reset}><Icon name="camera" /> Scan your own meal</button>
            ) : result.logged ? (
              <button className="btn btn-success btn-lg pop" onClick={() => onNavigate("today")}>
                <Icon name="check" /> Logged · see today
              </button>
            ) : (
              <button className="btn btn-primary btn-lg" onClick={logMeal}><Icon name="check" /> Log this meal</button>
            )}
            <button className="btn btn-outline" onClick={scanActions.reset} title="Start over (Esc)"><Icon name="camera" size={18} /> Scan another</button>
          </div>
        </div>
      </aside>

      <div className="results-main">
        <ErrorNote message={error} />
        {evaluation.warnings.map((w) => (
          <div key={w} className="alert alert-warn"><span className="alert-icon">🧂</span><span>{w}</span></div>
        ))}

        <div className="bento">
          <section className="card card-pad span-7">
            <div className="card-head">
              <span className="card-icon tone-leaf"><Icon name="scan" size={18} /></span>
              <div><h3>What's on the plate</h3><small>Fix a portion with the slider, or click a match to change it</small></div>
            </div>
            <ul className="items">
              {items.map((item, i) => {
                const removed = item.estimated_grams === 0;
                const max = Math.max(600, Math.round((item.estimated_grams || 100) * 3));
                return (
                  <li key={i} className={removed ? "removed" : ""}>
                    <span className="item-avatar" style={{ background: gradientFor(item.name) }}>{item.name[0]}</span>
                    <div className="item-body">
                      <div className="item-top">
                        <div>
                          <strong>{item.name}</strong>
                          <small>{item.portion_description}{!sample && <> · <span className="conf">{Math.round(item.confidence * 100)}% sure</span></>}</small>
                        </div>
                        <span className="item-kcal">{Math.round(scaled[i]?.nutrients.calories ?? 0)}<small> kcal</small></span>
                      </div>
                      {!sample && (
                        <div className="match-row">
                          <button className={`match-btn ${item.match ? "" : "missing"}`} onClick={() => setPicking(picking === i ? null : i)}
                            title="Change which food this is matched to">
                            📚 {item.match ? item.match.description : "Not found in the database: pick a match"}
                            <Icon name="chevron" size={14} />
                          </button>
                          {picking === i && <MatchPicker item={item} onPick={(f) => chooseMatch(i, f)} onClose={() => setPicking(null)} />}
                        </div>
                      )}
                      <div className="item-portion">
                        <input type="range" min="0" max={max} step="5"
                          value={item.estimated_grams} aria-label={`Portion of ${item.name} in grams`}
                          style={{ "--fill": `${(item.estimated_grams / max) * 100}%` }}
                          onChange={(e) => setItem(i, { estimated_grams: Number(e.target.value) })} />
                        <span className="grams">{Math.round(item.estimated_grams)} g</span>
                        <button className="icon-btn" title={removed ? "Add back" : "Remove item"}
                          aria-label={removed ? `Add ${item.name} back` : `Remove ${item.name}`}
                          onClick={() => setItem(i, { estimated_grams: removed ? 100 : 0 })}>
                          <Icon name={removed ? "undo" : "x"} size={15} />
                        </button>
                      </div>
                      {item.allergens.length > 0 && (
                        <div className="item-tags">
                          {item.allergens.map((a) => (
                            <span key={a} className={`tag ${profile.allergens.includes(a) ? "tag-danger" : ""}`}>{a.replace("_", " ")}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
            {!sample && (
              <div className="match-row add-food">
                <button className="btn btn-outline btn-sm" onClick={() => setAdding(!adding)}>+ Add a food the AI missed</button>
                {adding && <MatchPicker item={{ name: "", alternatives: [] }} onPick={addFood} onClose={() => setAdding(false)} />}
              </div>
            )}
          </section>

          <section className="card card-pad span-5">
            <div className="card-head">
              <span className="card-icon tone-saffron">🔥</span>
              <div><h3>Calories & macros</h3><small>{dayPct}% of your {fmt(evaluation.targets.calories)} kcal day</small></div>
            </div>
            <MacroDonut split={evaluation.macro_split} calories={t.calories} totals={t} />
            <div className="kcal-sources">
              <h4>Where the calories come from</h4>
              {scaled
                .map((it, i) => ({ key: i, name: items[i]?.name || it.name, kcal: it.nutrients.calories }))
                .filter((it) => it.kcal > 0)
                .sort((x, y) => y.kcal - x.kcal)
                .map((it) => (
                  <div key={it.key} className="kcal-source">
                    <span>{it.name}</span>
                    <strong>{Math.round(it.kcal)} kcal · {Math.round((100 * it.kcal) / (t.calories || 1))}%</strong>
                    <div className="meter"><span style={{ width: `${(100 * it.kcal) / (t.calories || 1)}%` }} /></div>
                  </div>
                ))}
            </div>
          </section>

          <div className="span-6 stack">
            <AllergenPanel allergens={evaluation.allergens} hidden={analysis.hidden_allergen_warnings} avoid={profile.allergens} />
          </div>

          <section className="card card-pad span-6">
            {analysis.diet_compatibility.length > 0 && (
              <>
                <div className="card-head">
                  <span className="card-icon tone-leaf"><Icon name="leaf" size={18} /></span>
                  <div><h3>Diet check</h3><small>Against your restrictions</small></div>
                </div>
                <ul className="diet-list">
                  {analysis.diet_compatibility.map((d) => (
                    <li key={d.diet} className={d.compatible ? "ok" : "no"}>
                      <span className="diet-badge"><Icon name={d.compatible ? "check" : "x"} size={14} /></span>
                      <div><strong>{d.diet}</strong><small>{d.reason}</small></div>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <div className="card-head">
              <span className="card-icon tone-sky"><Icon name="sparkle" size={18} /></span>
              <div><h3>Smarter swaps</h3><small>Same meal, more nutrition</small></div>
            </div>
            {analysis.healthier_swaps.length ? (
              <ul className="swaps">
                {analysis.healthier_swaps.map((s, i) => <li key={s}><span className="swap-num">{i + 1}</span>{s}</li>)}
              </ul>
            ) : <p className="muted">Nothing to change. Great choice!</p>}
          </section>

          <section className="card card-pad span-12">
            <div className="card-head">
              <span className="card-icon tone-plum">🧪</span>
              <div><h3>Vitamins & minerals</h3><small>How this meal stacks up against your daily targets</small></div>
            </div>
            <NutrientRings nutrients={evaluation.nutrients} />
            {analysis.data_source && <p className="fine-print">Nutrient values from {analysis.data_source}, scaled to your portions.</p>}
          </section>
        </div>

        {evaluation.gaps.length > 0 && (
          <section className="stack">
            <SectionHeader eyebrow="Fill the gaps" title="What this meal is missing">
              Matched to your diet and allergens, with your favourite cuisines first.
            </SectionHeader>
            <div className="gap-grid">
              {evaluation.gaps.map((g) => (
                <GapCard key={g.nutrient} gap={g} onFindRecipes={(n) => onNavigate("recipes", { focus_nutrient: n })} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
