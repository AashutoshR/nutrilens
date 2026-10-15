import { useEffect, useState } from "react";
import { api } from "../api.js";
import { MEAL_EMOJI, NUTRIENT_EMOJI, cuisineEmoji, gradientFor } from "../theme.js";
import CookRecipe, { AllergenRows } from "./CookRecipe.jsx";
import { ErrorNote, Icon, fmt, useFitSticky } from "./ui.jsx";

export default function RecipesPage({ meta, profile, params, aiConnected, health }) {
  // Recipes come from the recipe database when it's installed (instant), otherwise the AI writes them.
  const fromDatabase = !!health?.recipe_database;
  const ai = { available: !!health?.recipes_available, fromDatabase };
  const [mode, setMode] = useState(params?.mode || "recipes");
  // One allergy choice shared by the recipe finder and the meal planner.
  const [avoid, setAvoid] = useState(profile.allergens);

  return (
    <div className="page page-wide">
      <header className="page-head">
        <span className="eyebrow">{fromDatabase ? "Recipe finder · 500,000 real recipes" : "AI kitchen"}</span>
        <h1 className="display page-title">What should I <em>cook</em>?</h1>
        <p className="lead">
          Recipes and meal plans made for you{profile.diets.length ? `: ${profile.diets.map((d) => meta.diets[d].toLowerCase()).join(", ")}` : ""}.
          Pick any allergies and we'll leave out every recipe that contains, or may contain, them.
        </p>
      </header>
      <div className="workbench">
        {mode === "recipes"
          ? <RecipeFinder meta={meta} profile={profile} params={params} ai={ai} avoid={avoid} setAvoid={setAvoid} switcher={<ModeSwitch mode={mode} setMode={setMode} />} />
          : <PlanBuilder meta={meta} profile={profile} ai={ai} avoid={avoid} setAvoid={setAvoid} switcher={<ModeSwitch mode={mode} setMode={setMode} />} />}
      </div>
    </div>
  );
}

function ModeSwitch({ mode, setMode }) {
  return (
    <div className="segmented segmented-full" role="tablist">
      <button type="button" role="tab" aria-selected={mode === "recipes"} className={mode === "recipes" ? "active" : ""} onClick={() => setMode("recipes")}>👩‍🍳 Recipes</button>
      <button type="button" role="tab" aria-selected={mode === "plan"} className={mode === "plan" ? "active" : ""} onClick={() => setMode("plan")}>📅 Meal plan</button>
    </div>
  );
}

// Ctrl+Enter submits the form from anywhere in the panel.
const submitOnCtrlEnter = (submit) => (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    submit();
  }
};

const labels = (meta, keys) => keys.map((a) => meta.allergens[a].label).join(", ");

/** "Allergies to avoid" toggles; recipes with (or possibly with) a selected allergen are left out. */
function AvoidPicker({ meta, value, onChange }) {
  const toggle = (k) => onChange(value.includes(k) ? value.filter((a) => a !== k) : [...value, k]);
  return (
    <div className="field avoid-field">
      <span className="avoid-label">
        Allergies to avoid
        {value.length > 0 && <button type="button" className="link-btn" onClick={() => onChange([])}>Clear</button>}
      </span>
      <div className="chips">
        {Object.entries(meta.allergens).map(([k, a]) => (
          <button type="button" key={k} className={`chip chip-toggle chip-avoid ${value.includes(k) ? "on" : ""}`}
            aria-pressed={value.includes(k)} onClick={() => toggle(k)}>
            {a.icon} {a.label}
          </button>
        ))}
      </div>
      <small className="muted">
        {value.length
          ? `Hiding recipes that contain or may contain ${labels(meta, value).toLowerCase()}.`
          : "Nothing selected, so every recipe shows the allergens it has."}
      </small>
    </div>
  );
}

function EmptyResults({ emoji, title, text, children }) {
  return (
    <div className="results-empty">
      <span aria-hidden="true">{emoji}</span>
      <h3 className="display">{title}</h3>
      <p className="muted">{text}</p>
      {children}
    </div>
  );
}

function Unavailable({ what }) {
  return (
    <EmptyResults emoji="🍳" title={`${what} aren't available yet`}
      text="The recipe collection is still being set up. Please check back soon." />
  );
}

function RecipeFinder({ meta, profile, params, switcher, ai, avoid, setAvoid }) {
  const [cooking, setCooking] = useState(null);
  const [form, setForm] = useState({
    cuisine: "", focus_nutrient: params?.focus_nutrient || "", meal_type: "", max_minutes: "", ingredients: "",
    count: ai.fromDatabase ? 6 : 3,
  });
  const [avoided, setAvoided] = useState([]);
  const panelRef = useFitSticky();
  const [recipes, setRecipes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  useEffect(() => {
    if (params?.focus_nutrient && ai.available) submit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(e) {
    e?.preventDefault();
    if (!ai.available) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.recipes({
        cuisine: form.cuisine || null,
        focus_nutrient: form.focus_nutrient || null,
        meal_type: form.meal_type || null,
        max_minutes: form.max_minutes ? Number(form.max_minutes) : null,
        ingredients_on_hand: form.ingredients.split(",").map((s) => s.trim()).filter(Boolean),
        count: Number(form.count),
        avoid_allergens: avoid,
      });
      setRecipes(res.recipes);
      setAvoided(avoid);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const cuisines = [...new Set([...profile.cuisines, ...meta.cuisines])];

  return (
    <>
      <aside className="panel form-panel" ref={panelRef}>
      {switcher}
      <form className="finder" onSubmit={submit} onKeyDown={submitOnCtrlEnter(submit)}>
        <div className="finder-grid">
          <label className="field">
            <span>Cuisine</span>
            <select value={form.cuisine} onChange={set("cuisine")}>
              <option value="">Any (my favourites)</option>
              {cuisines.map((c) => <option key={c} value={c}>{cuisineEmoji(c)} {c}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Rich in</span>
            <select value={form.focus_nutrient} onChange={set("focus_nutrient")}>
              <option value="">No preference</option>
              {meta.gap_nutrients.map((k) => <option key={k} value={k}>{NUTRIENT_EMOJI[k]} {meta.nutrients[k].label}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Meal</span>
            <select value={form.meal_type} onChange={set("meal_type")}>
              <option value="">Any</option>
              {["breakfast", "lunch", "dinner", "snack", "dessert"].map((m) => (
                <option key={m} value={m}>{MEAL_EMOJI[m]} {m[0].toUpperCase() + m.slice(1)}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Ready in</span>
            <select value={form.max_minutes} onChange={set("max_minutes")}>
              <option value="">Any time</option>
              {[15, 30, 45, 60].map((m) => <option key={m} value={m}>Under {m} min</option>)}
            </select>
          </label>
        </div>
        <label className="field">
          <span>Ingredients you already have <small className="muted">(optional)</small></span>
          <input value={form.ingredients} onChange={set("ingredients")} placeholder="spinach, chickpeas, rice…" />
        </label>
        <AvoidPicker meta={meta} value={avoid} onChange={setAvoid} />
        <div className="finder-foot">
          <button className="btn btn-primary btn-lg" disabled={loading}>
            <Icon name="sparkle" /> {!ai.available ? "Recipes unavailable" : loading ? "Finding recipes…" : "Find recipes"}
          </button>
          <small className="muted"><span className="key-hint"><kbd>Ctrl</kbd> <kbd>Enter</kbd> · </span>matched to your diet</small>
        </div>
      </form>
      </aside>
      <section className="detail-panel">
        <ErrorNote message={error} onRetry={submit} />
        {loading && <SkeletonCards />}
        {!ai.available && <Unavailable what="Recipes" />}
        {ai.available && !loading && !recipes && !error && (
          <EmptyResults emoji="👩‍🍳" title="Your recipes will appear here"
            text="Pick a cuisine, a nutrient to boost or what's in your fridge, then hit Find recipes." />
        )}
        {!loading && recipes?.length === 0 && (
          <EmptyResults emoji="🔎" title="No recipes match all of that"
            text={`Try a different cuisine, remove the time limit, or clear the ingredients you entered${avoided.length ? ". Avoiding several allergens also narrows the choice" : ""}.`} />
        )}
        {!loading && recipes?.length > 0 && (
          <>
            {avoided.length > 0 && (
              <p className="safe-banner">🛡️ Every recipe here is free of <strong>{labels(meta, avoided).toLowerCase()}</strong>, including "may contain" ingredients.</p>
            )}
            <div className="recipe-grid">
              {recipes.map((r, i) => <RecipeCard key={r.id ?? r.name} recipe={r} meta={meta} profile={profile} index={i} onCook={setCooking} />)}
            </div>
          </>
        )}
      </section>
      {cooking && <CookRecipe recipe={cooking} meta={meta} profile={profile} onClose={() => setCooking(null)} />}
    </>
  );
}

function RecipeCard({ recipe: r, meta, profile, index, onCook }) {
  const total = r.prep_minutes + r.cook_minutes;
  return (
    <article className="recipe-card" style={{ "--i": index }}>
      <button className="recipe-cover" style={{ background: gradientFor(r.name) }} onClick={() => onCook(r)} aria-label={`Cook ${r.name}`}>
        {r.image
          ? <img className="cover-photo" src={r.image} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.display = "none"; }} />
          : <span className="cover-emoji" aria-hidden="true">{cuisineEmoji(r.cuisine)}</span>}
        <div className="cover-badges">
          {total > 0 && <span><Icon name="clock" size={14} /> {total} min</span>}
          <span>🔥 {fmt(r.per_serving.calories)} kcal</span>
        </div>
      </button>
      <div className="recipe-content">
        <div className="chips">
          <span className="chip chip-brand">{r.cuisine}</span>
          {r.diet_tags.slice(0, 3).map((t) => <span key={t} className="chip chip-soft">{t}</span>)}
        </div>
        <h3 className="display">{r.name}</h3>
        <p className="muted">{r.description}</p>
        <div className="macro-pills">
          <span><strong>{fmt(r.per_serving.protein_g)}g</strong>protein</span>
          <span><strong>{fmt(r.per_serving.carbs_g)}g</strong>carbs</span>
          <span><strong>{fmt(r.per_serving.fat_g)}g</strong>fat</span>
          <span><strong>{fmt(r.per_serving.fiber_g)}g</strong>fiber</span>
          <span><strong>{fmt(r.per_serving.calories)}</strong>kcal</span>
        </div>
        {r.highlight_nutrients.length > 0 && (
          <p className="rich-in">✨ Rich in <strong>{r.highlight_nutrients.join(" · ")}</strong></p>
        )}
        <AllergenRows recipe={r} meta={meta} profile={profile} />
        <button className="btn btn-primary btn-sm recipe-toggle" onClick={() => onCook(r)}>
          👩‍🍳 Cook this · serves {r.servings}
        </button>
      </div>
    </article>
  );
}

function PlanBuilder({ meta, profile, switcher, ai, avoid, setAvoid }) {
  const [cookingId, setCookingId] = useState(null);
  const panelRef = useFitSticky();
  const [days, setDays] = useState(3);
  const [focus, setFocus] = useState([]);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [checked, setChecked] = useState({});

  const toggle = (k) => setFocus(focus.includes(k) ? focus.filter((f) => f !== k) : [...focus, k]);

  async function submit(e) {
    e?.preventDefault();
    if (!ai.available) return;
    setLoading(true);
    setError("");
    try {
      setPlan(await api.mealPlan({ days, focus_nutrients: focus, cuisines: profile.cuisines, avoid_allergens: avoid }));
      setChecked({});
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const bought = Object.values(checked).filter(Boolean).length;

  return (
    <>
      <aside className="panel form-panel" ref={panelRef}>
      {switcher}
      <form className="finder" onSubmit={submit} onKeyDown={submitOnCtrlEnter(submit)}>
        <div className="field">
          <span>How many days?</span>
          <div className="day-picker">
            {[1, 3, 5, 7].map((d) => (
              <button type="button" key={d} className={days === d ? "active" : ""} onClick={() => setDays(d)} aria-pressed={days === d}>
                <strong>{d}</strong><small>{d === 1 ? "day" : "days"}</small>
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <span>Boost these nutrients <small className="muted">(optional)</small></span>
          <div className="chips">
            {meta.gap_nutrients.map((k) => (
              <button type="button" key={k} className={`chip chip-toggle ${focus.includes(k) ? "on" : ""}`}
                aria-pressed={focus.includes(k)} onClick={() => toggle(k)}>
                {NUTRIENT_EMOJI[k]} {meta.nutrients[k].label}
              </button>
            ))}
          </div>
        </div>
        <AvoidPicker meta={meta} value={avoid} onChange={setAvoid} />
        <div className="finder-foot">
          <button className="btn btn-primary btn-lg" disabled={loading}>
            <Icon name="sparkle" /> {!ai.available ? "Meal plans unavailable" : loading ? "Planning your meals…" : "Build my plan"}
          </button>
          <small className="muted">
            Targets {profile.calorie_target} kcal a day{profile.cuisines.length ? ` · inspired by ${profile.cuisines.join(", ")}` : ""}
          </small>
        </div>
      </form>
      </aside>
      <section className="detail-panel">
      <ErrorNote message={error} onRetry={submit} />
      {loading && <SkeletonCards />}
      {!ai.available && <Unavailable what="Meal plans" />}
      {ai.available && !loading && !plan && !error && (
        <EmptyResults emoji="📅" title="Your meal plan will appear here"
          text="Choose how many days and any nutrients to boost. You'll get every meal plus a shopping list." />
      )}
      {!loading && plan && (
        <div className="plan stack">
          <header className="plan-head">
            <h2 className="display">{plan.title}</h2>
            {plan.notes && <p className="muted">{plan.notes}</p>}
          </header>
          <div className="plan-days">
            {plan.days.map((d, i) => (
              <section key={d.day} className="plan-day" style={{ "--i": i }}>
                <header>
                  <div className="day-badge"><small>Day</small><strong>{d.day}</strong></div>
                  <div className="day-title"><h3>{d.theme}</h3><small>{fmt(d.total_calories)} kcal · {fmt(d.total_protein_g)} g protein</small></div>
                </header>
                <ul>
                  {d.meals.map((m) => (
                    <li key={m.meal_type + m.name} className={m.recipe_id ? "cookable" : ""}
                      onClick={() => m.recipe_id && setCookingId(m.recipe_id)} title={m.recipe_id ? "See how to cook it" : undefined}>
                      <span className="slot-emoji" aria-hidden="true">{MEAL_EMOJI[m.meal_type]}</span>
                      <div>
                        <small className="slot cap">{m.meal_type}</small>
                        <strong>{m.name}</strong>
                        {m.description && <p>{m.description}</p>}
                        <span className="slot-meta">
                          {cuisineEmoji(m.cuisine)} {m.cuisine} · {fmt(m.calories)} kcal{m.iron_mg != null ? ` · ${fmt(m.iron_mg)} mg iron` : ""}
                        </span>
                        {m.allergens.length > 0 && (
                          <span className="slot-allergens">
                            Contains {m.allergens.map((a) => <span key={a} className={profile.allergens.includes(a) ? "tag tag-danger" : "tag"}>{meta.allergens[a].icon} {meta.allergens[a].label}</span>)}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
                <div className="tip"><span aria-hidden="true">💡</span><p>{d.tip}</p></div>
              </section>
            ))}
          </div>
          <section className="card card-pad">
            <div className="card-head">
              <span className="card-icon tone-leaf">🛒</span>
              <div><h3>Shopping list</h3><small>{bought} of {plan.shopping_list.length} in the basket</small></div>
            </div>
            <div className="meter"><span style={{ width: `${(100 * bought) / plan.shopping_list.length}%` }} /></div>
            <ul className="shopping">
              {plan.shopping_list.map((s) => (
                <li key={s}>
                  <label className={checked[s] ? "done" : ""}>
                    <input type="checkbox" checked={!!checked[s]} onChange={() => setChecked({ ...checked, [s]: !checked[s] })} />
                    <span>{s}</span>
                  </label>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      </section>
      {cookingId && <CookRecipe recipeId={cookingId} meta={meta} profile={profile} onClose={() => setCookingId(null)} />}
    </>
  );
}

function SkeletonCards() {
  return (
    <div className="recipe-grid" aria-hidden="true">
      {[0, 1, 2].map((i) => <div key={i} className="skeleton" />)}
    </div>
  );
}
