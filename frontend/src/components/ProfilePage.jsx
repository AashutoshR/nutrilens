import { useEffect, useState } from "react";
import { api } from "../api.js";
import { CUISINE_EMOJI, DIET_EMOJI, GOALS, NUTRIENT_EMOJI } from "../theme.js";
import { ErrorNote, Icon, fmt } from "./ui.jsx";

const TARGET_KEYS = ["calories", "protein_g", "fiber_g", "iron_mg", "calcium_mg", "vitamin_d_mcg"];

export default function ProfilePage({ meta, profile, onSaved }) {
  const [form, setForm] = useState(profile);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [targets, setTargets] = useState(null);

  const loadTargets = () => api.today().then((d) => setTargets(d.evaluation.targets)).catch(() => {});
  useEffect(() => { loadTargets(); }, []);

  const update = (patch) => setForm({ ...form, ...patch });
  const dirty = JSON.stringify(form) !== JSON.stringify(profile);
  const toggle = (key, value) =>
    update({ [key]: form[key].includes(value) ? form[key].filter((v) => v !== value) : [...form[key], value] });

  async function save(e) {
    e?.preventDefault();
    setSaving(true);
    setError("");
    try {
      const p = await api.saveProfile({ ...form, age: Number(form.age), calorie_target: Number(form.calorie_target) });
      onSaved(p);
      setForm(p);
      loadTargets();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  // Ctrl+S saves, as in any desktop app.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty && !saving) save();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const initials = form.name.trim().split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  const summary = [
    form.diets.map((d) => meta.diets[d]).join(", "),
    form.allergens.length ? `avoids ${form.allergens.map((a) => meta.allergens[a].label.toLowerCase()).join(", ")}` : "",
    form.cuisines.length ? `loves ${form.cuisines.join(", ")}` : "",
  ].filter(Boolean).join(" · ");

  return (
    <div className="page page-wide">
      <form onSubmit={save} className="stack">
        <section className="profile-hero">
          <div className="avatar" aria-hidden="true">{initials || "🙂"}</div>
          <div className="profile-id">
            <span className="eyebrow">Your profile</span>
            <input className="name-input display" value={form.name} onChange={(e) => update({ name: e.target.value })}
              placeholder="What should we call you?" aria-label="Your name" />
            <p className="muted">{summary || "Tell us how you eat and NutriLens will tailor every alert, target and suggestion."}</p>
          </div>
          <div className="profile-save">
            <button className={`btn btn-lg ${dirty ? "btn-primary" : "btn-success"}`} disabled={saving || !dirty}>
              <Icon name="check" /> {saving ? "Saving…" : dirty ? "Save changes" : "All saved"}
            </button>
            <small className="muted">{dirty ? <>You have unsaved changes<span className="key-hint"> · <kbd>Ctrl</kbd> <kbd>S</kbd></span></> : "Your profile is up to date"}</small>
          </div>
        </section>
        <ErrorNote message={error} />

        <div className="bento">
          <section className="card card-pad span-7">
            <div className="card-head">
              <span className="card-icon tone-sky"><Icon name="user" size={18} /></span>
              <div><h3>About you</h3><small>Used to calculate your daily targets</small></div>
            </div>
            <div className="field">
              <span>Sex</span>
              <div className="segmented">
                {[["female", "Female"], ["male", "Male"], ["other", "Other"]].map(([v, l]) => (
                  <button type="button" key={v} className={form.sex === v ? "active" : ""} aria-pressed={form.sex === v}
                    onClick={() => update({ sex: v })}>{l}</button>
                ))}
              </div>
            </div>
            <div className="field-row">
              <label className="field">
                <span>Age</span>
                <input type="number" min="13" max="110" value={form.age} onChange={(e) => update({ age: e.target.value })} />
              </label>
              <label className="field grow">
                <span>Daily calories <strong className="cal-value">{form.calorie_target} kcal</strong></span>
                <input type="range" min="1200" max="4000" step="50" value={form.calorie_target}
                  style={{ "--fill": `${((form.calorie_target - 1200) / 2800) * 100}%` }}
                  onChange={(e) => update({ calorie_target: Number(e.target.value) })} />
              </label>
            </div>
            <div className="field">
              <span>Goal</span>
              <div className="goal-grid">
                {GOALS.map((g) => (
                  <button type="button" key={g.id} className={`goal ${form.goal === g.id ? "active" : ""}`}
                    aria-pressed={form.goal === g.id} onClick={() => update({ goal: g.id })}>
                    <span aria-hidden="true">{g.emoji}</span>
                    <strong>{g.label}</strong>
                    <small>{g.hint}</small>
                  </button>
                ))}
              </div>
            </div>
          </section>

          <section className="card card-pad span-5 targets-card">
            <div className="card-head">
              <span className="card-icon tone-saffron">🎯</span>
              <div><h3>Your daily targets</h3><small>{dirty ? "Save to update" : "Based on your saved profile"}</small></div>
            </div>
            {targets ? (
              <div className="targets">
                {TARGET_KEYS.map((k) => (
                  <div key={k} className="target">
                    <span aria-hidden="true">{NUTRIENT_EMOJI[k]}</span>
                    <strong>{fmt(targets[k])}<small> {meta.nutrients[k].unit}</small></strong>
                    <small>{meta.nutrients[k].label}</small>
                  </div>
                ))}
              </div>
            ) : <p className="muted">Loading…</p>}
            <p className="fine-print">Based on US Dietary Reference Intakes for adults. Your doctor or dietitian may set different targets.</p>
          </section>

          <section className="card card-pad span-12">
            <div className="card-head">
              <span className="card-icon tone-leaf"><Icon name="leaf" size={18} /></span>
              <div><h3>How you eat</h3><small>Pick any that apply</small></div>
            </div>
            <div className="chips">
              {Object.entries(meta.diets).map(([k, label]) => (
                <button type="button" key={k} className={`chip chip-toggle ${form.diets.includes(k) ? "on" : ""}`}
                  aria-pressed={form.diets.includes(k)} onClick={() => toggle("diets", k)}>
                  <span aria-hidden="true">{DIET_EMOJI[k]}</span> {label}
                </button>
              ))}
            </div>
          </section>

          <section className="card card-pad span-12">
            <div className="card-head">
              <span className="card-icon tone-tomato"><Icon name="shield" size={18} /></span>
              <div><h3>Allergens to avoid</h3><small>We'll warn you whenever a meal, recipe or plan contains these</small></div>
            </div>
            <div className="allergen-picker">
              {Object.entries(meta.allergens).map(([k, a]) => (
                <button type="button" key={k} className={`allergen-option ${form.allergens.includes(k) ? "on" : ""}`}
                  aria-pressed={form.allergens.includes(k)} onClick={() => toggle("allergens", k)}>
                  <span aria-hidden="true">{a.icon}</span>
                  <strong>{a.label}</strong>
                  {form.allergens.includes(k) && <Icon name="check" size={14} className="check" />}
                </button>
              ))}
            </div>
          </section>

          <section className="card card-pad span-12">
            <div className="card-head">
              <span className="card-icon tone-plum">🌍</span>
              <div><h3>Favourite cuisines</h3><small>We'll lean on these for dishes, recipes and plans</small></div>
            </div>
            <div className="chips">
              {meta.cuisines.map((c) => (
                <button type="button" key={c} className={`chip chip-toggle ${form.cuisines.includes(c) ? "on" : ""}`}
                  aria-pressed={form.cuisines.includes(c)} onClick={() => toggle("cuisines", c)}>
                  <span aria-hidden="true">{CUISINE_EMOJI[c] || "🍽️"}</span> {c}
                </button>
              ))}
            </div>
          </section>
        </div>

      </form>
    </div>
  );
}
