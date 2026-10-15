async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, options);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    let code;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg).join("; ");
      code = body.code;
    } catch {
      /* non-JSON error body */
    }
    const error = new Error(detail);
    error.code = code;
    throw error;
  }
  return res.status === 204 ? null : res.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request("/health"),
  meta: () => request("/meta"),
  profile: () => request("/profile"),
  saveProfile: (profile) => request("/profile", json("PUT", profile)),
  analyze: (blob) => {
    const form = new FormData();
    form.append("image", blob, "meal.jpg");
    return request("/analyze", { method: "POST", body: form });
  },
  analysisStatus: (jobId) => request(`/analyze/${jobId}`),
  describe: (meal) => request("/describe", json("POST", meal)),
  searchFoods: (q, branded = false) => request(`/foods/search?q=${encodeURIComponent(q)}&branded=${branded}`),
  getFood: (fdcId) => request(`/foods/${fdcId}`),
  samples: () => request("/samples"),
  analyzeSample: (id) => request(`/samples/${id}/analyze`, { method: "POST" }),
  evaluate: (items, scope = "meal") => request("/evaluate", json("POST", { items, scope })),
  logMeal: (meal) => request("/meals", json("POST", meal)),
  deleteMeal: (id) => request(`/meals/${id}`, { method: "DELETE" }),
  today: () => request("/today"),
  nutrient: (key) => request(`/nutrients/${key}`),
  recipes: (req) => request("/recipes", json("POST", req)),
  getRecipe: (id) => request(`/recipes/${id}`),
  completeMeasurements: (id) => request(`/recipes/${id}/measurements`, { method: "POST" }),
  mealPlan: (req) => request("/meal-plan", json("POST", req)),
};
