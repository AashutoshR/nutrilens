import { useEffect, useState } from "react";
import { api } from "../api.js";
import { NUTRIENT_BLURB, NUTRIENT_EMOJI } from "../theme.js";
import { ErrorNote, GapCard, Icon, Spinner, useFitSticky } from "./ui.jsx";

export default function NutrientsPage({ meta, onNavigate, initial }) {
  const [selected, setSelected] = useState(initial || "iron_mg");
  const [guide, setGuide] = useState(null);
  const listRef = useFitSticky();
  const [error, setError] = useState("");
  const keys = meta.gap_nutrients;

  useEffect(() => {
    setGuide(null);
    setError("");
    api.nutrient(selected).then(setGuide).catch((e) => setError(e.message));
  }, [selected]);

  // Arrow keys move through the list, like a desktop list view.
  function onListKey(e) {
    const i = keys.indexOf(selected);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = keys[(i + (e.key === "ArrowDown" ? 1 : -1) + keys.length) % keys.length];
      setSelected(next);
      document.getElementById(`nutrient-${next}`)?.focus();
    }
  }

  return (
    <div className="page page-wide">
      <header className="page-head">
        <span className="eyebrow">Nutrient guide</span>
        <h1 className="display page-title">Feeling low on something?</h1>
        <p className="lead">Pick a nutrient to see the richest foods and the most-loved dishes for it, filtered to your diet, allergens and favourite cuisines.</p>
      </header>

      <div className="workbench">
        <aside className="panel list-panel" ref={listRef}>
          <div className="panel-title"><span>Nutrients</span><small className="muted key-hint"><kbd>↑</kbd> <kbd>↓</kbd> to browse</small></div>
          <div className="nutrient-list" role="listbox" aria-label="Nutrients" onKeyDown={onListKey}>
            {keys.map((k) => (
              <button key={k} id={`nutrient-${k}`} role="option" aria-selected={selected === k} tabIndex={selected === k ? 0 : -1}
                className={`nutrient-row ${selected === k ? "active" : ""}`} onClick={() => setSelected(k)}>
                <span className="tile-emoji" aria-hidden="true">{NUTRIENT_EMOJI[k]}</span>
                <span className="row-text"><strong>{meta.nutrients[k].label}</strong><small>{NUTRIENT_BLURB[k]}</small></span>
                <Icon name="chevron" size={16} />
              </button>
            ))}
          </div>
        </aside>

        <section className="detail-panel">
          <ErrorNote message={error} />
          {!guide && !error && <Spinner />}
          {guide && <GapCard key={guide.nutrient} gap={guide} guide onFindRecipes={(n) => onNavigate("recipes", { focus_nutrient: n })} />}
        </section>
      </div>
    </div>
  );
}
