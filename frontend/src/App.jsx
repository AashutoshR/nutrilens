import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import NutrientsPage from "./components/NutrientsPage.jsx";
import ProfilePage from "./components/ProfilePage.jsx";
import RecipesPage from "./components/RecipesPage.jsx";
import ScanPage from "./components/ScanPage.jsx";
import TodayPage from "./components/TodayPage.jsx";
import { ErrorNote, Icon, Logo, Ring, Spinner, fmt } from "./components/ui.jsx";

const TABS = [
  { id: "scan", label: "Scan a meal", icon: "camera" },
  { id: "today", label: "Today", icon: "today" },
  { id: "nutrients", label: "Nutrient guide", icon: "leaf" },
  { id: "recipes", label: "Recipes & plans", icon: "recipe" },
  { id: "profile", label: "Profile", icon: "user" },
];

function readCollapsed() {
  try {
    return localStorage.getItem("nutrilens.sidebar") === "collapsed";
  } catch {
    return false;
  }
}

const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function App() {
  const [tab, setTab] = useState("scan");
  const [params, setParams] = useState(null);
  const [navKey, setNavKey] = useState(0);
  const [meta, setMeta] = useState(null);
  const [profile, setProfile] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [today, setToday] = useState(null);
  const [scan, setScan] = useState(null);
  const [toast, setToast] = useState(null);
  const tabRef = useRef(tab);
  tabRef.current = tab;
  const aiConnected = !!health?.ai_connected;

  const boot = () => {
    setError("");
    Promise.all([api.meta(), api.profile(), api.health()])
      .then(([m, p, h]) => { setMeta(m); setProfile(p); setHealth(h); })
      .catch(() => setError("Can't reach the NutriLens server. Is it running? Start it with start.bat."));
  };
  useEffect(boot, []);

  // Keep the sidebar's daily summary fresh whenever the user moves around the app.
  const refreshToday = () => api.today().then(setToday).catch(() => {});
  useEffect(() => { refreshToday(); }, [navKey]);

  function navigate(next, nextParams = null) {
    setTab(next);
    setParams(nextParams);
    setNavKey((k) => k + 1);
    document.querySelector(".main-area")?.scrollTo({ top: 0 });
  }

  useEffect(() => {
    const label = TABS.find((t) => t.id === tab)?.label;
    const ready = scan?.status === "done" && tab !== "scan" ? "✓ Meal ready · " : "";
    document.title = `${ready}${label} · NutriLens`;
  }, [tab, scan?.status]);

  // Alt+1…5 switches pages, like tabs in a desktop app.
  useEffect(() => {
    const onKey = (e) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return;
      const index = Number(e.key) - 1;
      if (TABS[index]) {
        e.preventDefault();
        navigate(TABS[index].id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Keyboard shortcut hints stay hidden until the user holds Alt.
  useEffect(() => {
    const root = document.documentElement;
    const show = (e) => {
      if (e.key !== "Alt") return;
      e.preventDefault(); // stop the browser from moving focus to its own menu
      root.classList.add("show-keys");
    };
    const hide = (e) => {
      if (!e || e.key === "Alt" || e.type === "blur") root.classList.remove("show-keys");
    };
    window.addEventListener("keydown", show);
    window.addEventListener("keyup", hide);
    window.addEventListener("blur", hide);
    return () => {
      window.removeEventListener("keydown", show);
      window.removeEventListener("keyup", hide);
      window.removeEventListener("blur", hide);
      root.classList.remove("show-keys");
    };
  }, []);

  // ---- The current scan lives here so it keeps running while the user browses other pages ----
  const scanActions = {
    setImage: (image) => setScan({ image, status: "ready" }),
    reset: () => setScan(null),
    showSample: (image, result) => setScan({ image, status: "done", result }),
    updateResult: (result) => setScan((s) => (s ? { ...s, result } : s)),
    analyze: async () => {
      if (!scan?.image?.blob) return;
      setScan((s) => ({ ...s, status: "uploading", error: null, result: null, elapsed: 0, itemsSeen: [] }));
      try {
        const { job_id } = await api.analyze(scan.image.blob);
        setScan((s) => ({ ...s, jobId: job_id, status: "looking" }));
      } catch (e) {
        setScan((s) => ({ ...s, status: "error", error: { detail: e.message, code: e.code } }));
      }
    },
  };

  useEffect(() => {
    if (!scan?.jobId || !["looking", "matching"].includes(scan.status)) return;
    let stopped = false;
    const poll = async () => {
      try {
        const job = await api.analysisStatus(scan.jobId);
        if (stopped) return;
        setScan((s) => (s?.jobId === job.id
          ? { ...s, status: job.status, elapsed: job.elapsed, itemsSeen: job.items_seen, result: job.result, error: job.error }
          : s));
        if (job.status === "done" && tabRef.current !== "scan") {
          setToast({ text: `Your meal is ready: ${job.result?.analysis?.dish_name || "see the results"}`, action: "scan" });
        }
        if (job.status === "error" && tabRef.current !== "scan") {
          setToast({ text: "The meal analysis didn't finish. Open Scan to try again.", action: "scan", kind: "error" });
        }
      } catch (e) {
        if (!stopped) setScan((s) => ({ ...s, status: "error", error: { detail: e.message, code: e.code } }));
      }
    };
    const t = setInterval(poll, 1500);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, [scan?.jobId, scan?.status]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 8000);
    return () => clearTimeout(t);
  }, [toast]);

  function toggleSidebar() {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem("nutrilens.sidebar", next ? "collapsed" : "expanded");
    } catch {
      /* storage unavailable: preference just won't persist */
    }
  }

  let page;
  if (error) page = <div className="page"><ErrorNote message={error} onRetry={boot} /></div>;
  else if (!meta || !profile) page = <div className="page"><Spinner label="Warming up the lens…" /></div>;
  else {
    const props = { meta, profile, params, aiConnected, health, onNavigate: navigate, onMealLogged: refreshToday };
    page = {
      scan: <ScanPage {...props} scan={scan} scanActions={scanActions} />,
      today: <TodayPage {...props} />,
      nutrients: <NutrientsPage {...props} initial={params?.nutrient} />,
      recipes: <RecipesPage {...props} />,
      profile: <ProfilePage {...props} onSaved={setProfile} />,
    }[tab];
  }

  const initials = profile?.name.trim().split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  const ev = today?.evaluation;
  const calPct = ev ? Math.round((100 * ev.totals.calories) / ev.targets.calories) : 0;
  const scanning = ["uploading", "looking", "matching"].includes(scan?.status);
  const scanReady = scan?.status === "done" && scan.result && !scan.result.sample && !scan.result.logged;

  return (
    <div className={`shell ${collapsed ? "collapsed" : ""}`}>
      <div className="ambient" aria-hidden="true"><span className="blob b1" /><span className="blob b2" /><span className="blob b3" /></div>

      <aside className="sidebar">
        <button className="brand" onClick={() => navigate("scan")} aria-label="NutriLens home">
          <Logo />
          <span className="brand-text">
            <strong>Nutri<em>Lens</em></strong>
            <small>Snap · Know · Nourish</small>
          </span>
        </button>

        <nav className="side-nav" aria-label="Main">
          {TABS.map((t, i) => (
            <button key={t.id} className={`side-item ${tab === t.id ? "active" : ""}`}
              aria-current={tab === t.id ? "page" : undefined} onClick={() => navigate(t.id)}
              title={`${t.label} (Alt+${i + 1})`}>
              <span className="side-icon"><Icon name={t.icon} size={20} /></span>
              <span className="side-label">{t.label}</span>
              {t.id === "scan" && (scanning || scanReady)
                ? <span className={`side-badge ${scanReady ? "ready" : ""}`}>{scanReady ? "Ready" : clock(scan.elapsed || 0)}</span>
                : <kbd className="side-kbd">Alt {i + 1}</kbd>}
            </button>
          ))}
        </nav>

        {scanning && tab !== "scan" && (
          <button className="scan-chip" onClick={() => navigate("scan")}>
            <span className="spinner spinner-dark" />
            <span><strong>Analysing your meal…</strong><small>{scan.status === "matching" ? "Matching foods to USDA data" : "AI is looking at your photo"}</small></span>
          </button>
        )}

        {ev && (
          <button className="today-widget" onClick={() => navigate("today")} title="Open today's summary">
            <Ring pct={calPct} size={58} stroke={7} color="var(--tomato)">
              <span className="tw-pct">{calPct}%</span>
            </Ring>
            <span className="tw-text">
              <small>Today</small>
              <strong>{fmt(ev.totals.calories)} <span>/ {fmt(ev.targets.calories)} kcal</span></strong>
              <span>{today.meals.length} {today.meals.length === 1 ? "meal" : "meals"} logged</span>
            </span>
          </button>
        )}

        <div className="side-foot">
          <button className={`me-card ${tab === "profile" ? "active" : ""}`} onClick={() => navigate("profile")} title="Edit profile">
            <span className="me">{initials || <Icon name="user" size={18} />}</span>
            <span className="me-text">
              <strong>{profile?.name || "Set up profile"}</strong>
              <small>{profile ? `${profile.calorie_target} kcal · ${profile.goal[0].toUpperCase()}${profile.goal.slice(1)}` : ""}</small>
            </span>
          </button>
          <button className="collapse-btn" onClick={toggleSidebar} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            <Icon name="chevron" size={18} className={collapsed ? "" : "flip"} />
          </button>
        </div>
      </aside>

      <div className="main-area">
        <main key={navKey}>{page}</main>
        <footer className="footer">
          <p>NutriLens gives estimates for general wellness, not medical advice. Nutrition data: USDA FoodData Central.
            Talk to a doctor or dietitian about deficiencies or allergies.</p>
        </footer>
      </div>

      {toast && (
        <div className="toast" role="status">
          <span aria-hidden="true">{toast.kind === "error" ? "⚠️" : "✅"}</span>
          <span>{toast.text}</span>
          <button className="btn btn-primary btn-sm" onClick={() => { setToast(null); navigate(toast.action); }}>View</button>
          <button className="icon-btn" aria-label="Dismiss" onClick={() => setToast(null)}><Icon name="x" size={14} /></button>
        </div>
      )}
    </div>
  );
}
