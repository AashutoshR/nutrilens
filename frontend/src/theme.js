// Visual vocabulary shared across pages: emoji, short blurbs and colour pairings.

export const NUTRIENT_EMOJI = {
  calories: "🔥", protein_g: "💪", carbs_g: "🍞", fat_g: "🥑", fiber_g: "🌾", sugar_g: "🍬",
  sodium_mg: "🧂", iron_mg: "🥬", calcium_mg: "🥛", vitamin_c_mg: "🍊", vitamin_d_mcg: "☀️",
  vitamin_b12_mcg: "⚡", potassium_mg: "🍌", magnesium_mg: "🌰", zinc_mg: "🦪", folate_mcg: "🥦",
};

export const NUTRIENT_BLURB = {
  iron_mg: "Energy & oxygen", calcium_mg: "Bones & teeth", vitamin_d_mcg: "The sunshine vitamin",
  vitamin_b12_mcg: "Nerves & blood", fiber_g: "Gut health", protein_g: "Muscle & fullness",
  vitamin_c_mg: "Immunity & glow", potassium_mg: "Heart & blood pressure", magnesium_mg: "Sleep & muscles",
  zinc_mg: "Immunity & healing", folate_mcg: "Cell growth",
};

export const CUISINE_EMOJI = {
  Indian: "🍛", Italian: "🍝", Mexican: "🌮", Chinese: "🥟", Japanese: "🍣", Thai: "🌶️", Korean: "🥢",
  Vietnamese: "🍜", Mediterranean: "🫒", "Middle Eastern": "🧆", Greek: "🥙", French: "🥐",
  American: "🍔", Ethiopian: "🫓", Caribbean: "🥥", Spanish: "🥘", British: "🫖", Bengali: "🐟",
  Indonesian: "🍢", Fusion: "✨", Snack: "🍎",
};

export const DIET_EMOJI = {
  vegetarian: "🥕", vegan: "🌱", pescatarian: "🐟", keto: "🥑", paleo: "🍖", gluten_free: "🌾",
  dairy_free: "🥛", halal: "☪️", kosher: "✡️", low_sodium: "🧂", diabetic_friendly: "🩺",
};

export const MEAL_EMOJI = { breakfast: "🌅", lunch: "☀️", dinner: "🌙", snack: "🍎", dessert: "🍰", drink: "🥤" };

export const GOALS = [
  { id: "maintain", label: "Maintain", emoji: "⚖️", hint: "Stay balanced" },
  { id: "lose", label: "Lose weight", emoji: "🏃", hint: "Gentle deficit" },
  { id: "gain", label: "Gain weight", emoji: "🍽️", hint: "Healthy surplus" },
  { id: "muscle", label: "Build muscle", emoji: "💪", hint: "Extra protein" },
];

// Muted produce tones, blended with the surface so they sit calmly in light and dark mode.
const GRADIENTS = [
  ["#e9c9a0", "#d9a98c"], ["#bcd8b4", "#9cc5ac"], ["#e6c0b4", "#d4a596"],
  ["#c9d3a8", "#aebf8e"], ["#ecd9a6", "#dcc08a"], ["#cfc8de", "#b6aecb"],
];

export function gradientFor(text = "") {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const [a, b] = GRADIENTS[h % GRADIENTS.length];
  return `linear-gradient(135deg, color-mix(in srgb, ${a} 55%, var(--surface-2)), color-mix(in srgb, ${b} 55%, var(--surface-2)))`;
}

export const cuisineEmoji = (c) => CUISINE_EMOJI[c] || "🍽️";

export function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}
