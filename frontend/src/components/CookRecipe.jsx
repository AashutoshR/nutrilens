import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import { cuisineEmoji, gradientFor } from "../theme.js";
import { Icon, Spinner, fmt } from "./ui.jsx";

/**
 * The whole recipe inside NutriLens: summary, ingredient checklist, step-by-step method, nutrition and allergens.
 * Pass `recipe` (from a search) or just `recipeId` (from a meal plan).
 */
export default function CookRecipe({ recipe: initial, recipeId, meta, profile, onClose }) {
  const id = initial?.id ?? recipeId;
  const [recipe, setRecipe] = useState(initial || null);
  const [error, setError] = useState("");
  const [measuring, setMeasuring] = useState(false);
  const [have, setHave] = useState({});
  const [doneSteps, setDoneSteps] = useState({});
  const closeBtn = useRef();

  // Open in front of everything: freeze the page behind it and take keyboard focus.
  useEffect(() => {
    const scrollers = [document.body, document.querySelector(".main-area")].filter(Boolean);
    const before = scrollers.map((el) => el.style.overflow);
    scrollers.forEach((el) => { el.style.overflow = "hidden"; });
    closeBtn.current?.focus({ preventScroll: true });
    return () => scrollers.forEach((el, i) => { el.style.overflow = before[i]; });
  }, []);

  useEffect(() => {
    if (!id) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const full = await api.getRecipe(id);
        if (cancelled) return;
        setRecipe(full);
        if (!full.measurements_estimated) {
          // The recipe data has amounts without units; fill them in once (then they're saved).
          setMeasuring(true);
          const measured = await api.completeMeasurements(id);
          if (!cancelled) setRecipe(measured);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setMeasuring(false);
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const r = recipe;
  const conflicts = r ? r.allergens.filter((a) => profile.allergens.includes(a)) : [];
  const maybe = r ? (r.may_contain || []).filter((a) => profile.allergens.includes(a)) : [];
  const haveCount = r ? r.ingredients.filter((_, i) => have[i]).length : 0;
  const stepsDone = r ? r.steps.filter((_, i) => doneSteps[i]).length : 0;
  const total = r ? r.prep_minutes + r.cook_minutes : 0;

  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal cook-modal" role="dialog" aria-modal="true" aria-label={r ? r.name : "Recipe"}>
        <button ref={closeBtn} className="icon-btn cook-close" onClick={onClose} aria-label="Close recipe" title="Close (Esc)"><Icon name="x" size={16} /></button>
        {!r && !error && <Spinner label="Opening recipe…" />}
        {error && <div className="alert alert-error" style={{ margin: 24 }}><span className="alert-icon">⚠️</span><span>{error}</span></div>}
        {r && (
          <>
            <header className="cook-hero">
              <div className="cook-photo" style={{ background: gradientFor(r.name) }}>
                {r.image
                  ? <img src={r.image} alt="" onError={(e) => { e.currentTarget.style.display = "none"; }} />
                  : <span aria-hidden="true">{cuisineEmoji(r.cuisine)}</span>}
              </div>
              <div className="cook-title">
                <div className="chips">
                  <span className="chip chip-brand">{cuisineEmoji(r.cuisine)} {r.cuisine}</span>
                  {r.diet_tags.slice(0, 3).map((t) => <span key={t} className="chip chip-soft">{t}</span>)}
                </div>
                <h2 className="display">{r.name}</h2>
                <p className="lead">{r.description}</p>
                <div className="cook-facts">
                  {total > 0 && <span><Icon name="clock" size={16} /> {total} min{r.prep_minutes ? ` (${r.prep_minutes} prep)` : ""}</span>}
                  <span>Serves {r.servings}</span>
                  <span>🔥 {fmt(r.per_serving.calories)} kcal per serving</span>
                </div>
              </div>
            </header>

            {conflicts.length > 0 && (
              <div className="alert alert-danger cook-alert"><span className="alert-icon">⚠️</span>
                <span>Contains <strong>{conflicts.map((a) => meta.allergens[a].label).join(", ")}</strong>, which you avoid.</span></div>
            )}
            {maybe.length > 0 && (
              <div className="alert alert-warn cook-alert"><span className="alert-icon">⚠️</span>
                <span>May contain <strong>{maybe.map((a) => meta.allergens[a].label).join(", ")}</strong>, which you avoid. Check the packets before cooking.</span></div>
            )}

            <div className="cook-body">
              <section className="cook-ingredients">
                <div className="cook-head">
                  <h3>Ingredients</h3>
                  <small className="muted">{haveCount} of {r.ingredients.length} ready</small>
                </div>
                {measuring && <p className="measuring"><span className="spinner spinner-dark" /> Adding measurements…</p>}
                <ul className="ingredients">
                  {r.ingredients.map((ing, i) => (
                    <li key={i}>
                      <label>
                        <input type="checkbox" checked={!!have[i]} onChange={() => setHave({ ...have, [i]: !have[i] })} />
                        <span className={have[i] ? "done" : ""}>{ing}</span>
                      </label>
                    </li>
                  ))}
                </ul>
                {r.measurements_estimated && (
                  <p className="fine-print">Measurements were completed by AI from the recipe's amounts and method, so check them as you cook.</p>
                )}

                <h3 className="cook-sub">Per serving</h3>
                <div className="macro-pills">
                  <span><strong>{fmt(r.per_serving.calories)}</strong>kcal</span>
                  <span><strong>{fmt(r.per_serving.protein_g)}g</strong>protein</span>
                  <span><strong>{fmt(r.per_serving.carbs_g)}g</strong>carbs</span>
                  <span><strong>{fmt(r.per_serving.fat_g)}g</strong>fat</span>
                  <span><strong>{fmt(r.per_serving.fiber_g)}g</strong>fiber</span>
                </div>
                <h3 className="cook-sub">Allergens</h3>
                <AllergenRows recipe={r} meta={meta} profile={profile} />
              </section>

              <section className="cook-method">
                <div className="cook-head">
                  <h3>Method</h3>
                  <small className="muted">{stepsDone} of {r.steps.length} steps done · click a step when it's done</small>
                </div>
                <div className="meter"><span style={{ width: `${(100 * stepsDone) / (r.steps.length || 1)}%` }} /></div>
                <ol className="cook-steps">
                  {r.steps.map((s, i) => (
                    <li key={i} className={doneSteps[i] ? "done" : ""}>
                      <button onClick={() => setDoneSteps({ ...doneSteps, [i]: !doneSteps[i] })} aria-pressed={!!doneSteps[i]}>
                        <span className="step-num">{doneSteps[i] ? <Icon name="check" size={14} /> : i + 1}</span>
                        <p>{s}</p>
                      </button>
                    </li>
                  ))}
                </ol>
                {stepsDone === r.steps.length && r.steps.length > 0 && <p className="cook-finished">🎉 All done. Enjoy your meal!</p>}
              </section>
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}

/** What a recipe contains and what it may contain; allergens from the profile are highlighted. */
export function AllergenRows({ recipe: r, meta, profile }) {
  const mine = (a) => (profile.allergens.includes(a) ? "tag tag-danger" : "tag");
  const may = r.may_contain || [];
  return (
    <div className="allergen-rows">
      <p>
        <span className="allergen-key">Contains</span>
        {r.allergens.length
          ? r.allergens.map((a) => <span key={a} className={mine(a)}>{meta.allergens[a].icon} {meta.allergens[a].label}</span>)
          : <span className="tag tag-ok">None of the 14 major allergens</span>}
      </p>
      {may.length > 0 && (
        <p title="An ingredient here is often made with, or near, these allergens. Check the packet.">
          <span className="allergen-key">May contain</span>
          {may.map((a) => <span key={a} className={`${mine(a)} tag-maybe`}>{meta.allergens[a].icon} {meta.allergens[a].label}</span>)}
        </p>
      )}
    </div>
  );
}
