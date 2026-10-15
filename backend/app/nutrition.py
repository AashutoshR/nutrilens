"""Deterministic nutrition math: portion scaling, daily targets, allergen checks and gap detection."""

from __future__ import annotations

from .knowledge import ALLERGENS, GAP_NUTRIENTS, NUTRIENTS, suggestions_for
from .schemas import ItemInput, Nutrients, Profile

NUTRIENT_KEYS = list(Nutrients.model_fields)

# A meal is assumed to cover roughly a third of the day.
MEAL_SHARE = 1 / 3


def daily_targets(p: Profile) -> dict[str, float]:
    """Adult daily targets based on US Dietary Reference Intakes, adjusted for goal and diet."""
    female = p.sex == "female"
    male = p.sex == "male"

    def by_sex(f: float, m: float) -> float:
        return f if female else m if male else (f + m) / 2

    cal = float(p.calorie_target)
    protein_ratio = {"muscle": 0.30, "lose": 0.25}.get(p.goal, 0.20)
    if "keto" in p.diets:
        carb_ratio, fat_ratio = 0.05, 0.70
    else:
        carb_ratio, fat_ratio = 0.50, 0.30

    return {
        "calories": cal,
        "protein_g": max(by_sex(46, 56), cal * protein_ratio / 4),
        "carbs_g": cal * carb_ratio / 4,
        "fat_g": cal * fat_ratio / 9,
        "fiber_g": 14 * cal / 1000,
        "sugar_g": cal * 0.10 / 4,
        "sodium_mg": 1500 if "low_sodium" in p.diets else 2300,
        "iron_mg": 8 if p.age > 50 else by_sex(18, 8),
        "calcium_mg": 1200 if (female and p.age > 50) or p.age > 70 else 1000,
        "vitamin_c_mg": by_sex(75, 90),
        "vitamin_d_mcg": 20 if p.age > 70 else 15,
        "vitamin_b12_mcg": 2.4,
        "potassium_mg": by_sex(2600, 3400),
        "magnesium_mg": by_sex(315, 410),
        "zinc_mg": by_sex(8, 11),
        "folate_mcg": 400,
    }


def scale_item(item: ItemInput) -> dict[str, float]:
    factor = item.estimated_grams / 100
    per100 = item.per_100g.model_dump()
    return {k: round(per100[k] * factor, 2) for k in NUTRIENT_KEYS}


def evaluate(items: list[ItemInput], profile: Profile, scope: str = "meal") -> dict:
    """Totals, %DV, macro split, allergen conflicts and nutrient gaps with food suggestions."""
    targets = daily_targets(profile)
    share = MEAL_SHARE if scope == "meal" else 1.0

    scaled_items = []
    totals = {k: 0.0 for k in NUTRIENT_KEYS}
    for item in items:
        nutrients = scale_item(item)
        for k in NUTRIENT_KEYS:
            totals[k] += nutrients[k]
        scaled_items.append({**item.model_dump(), "nutrients": nutrients})
    totals = {k: round(v, 1) for k, v in totals.items()}

    rows = []
    for k in NUTRIENT_KEYS:
        meta = NUTRIENTS[k]
        target = targets[k]
        pct_daily = 100 * totals[k] / target if target else 0
        pct_of_share = pct_daily / share
        if meta["kind"] == "limit":
            status = "high" if pct_of_share > 120 else "ok"
        elif pct_of_share < 40:
            status = "low"
        elif pct_of_share > 160 and k == "calories":
            status = "high"
        else:
            status = "good"
        rows.append({
            "key": k,
            "label": meta["label"],
            "unit": meta["unit"],
            "kind": meta["kind"],
            "amount": totals[k],
            "daily_target": round(target, 1),
            "pct_daily": round(pct_daily),
            "pct_of_share": round(pct_of_share),
            "status": status,
        })
    by_key = {r["key"]: r for r in rows}

    macro_cal = {
        "protein": totals["protein_g"] * 4,
        "carbs": totals["carbs_g"] * 4,
        "fat": totals["fat_g"] * 9,
    }
    macro_sum = sum(macro_cal.values()) or 1
    macro_split = {k: round(100 * v / macro_sum) for k, v in macro_cal.items()}

    found: dict[str, list[str]] = {}
    for item in items:
        for a in item.allergens:
            found.setdefault(a, []).append(item.name)
    allergens = [
        {
            "key": a,
            "label": ALLERGENS[a]["label"],
            "icon": ALLERGENS[a]["icon"],
            "items": names,
            "conflict": a in profile.allergens,
        }
        for a, names in sorted(found.items(), key=lambda kv: (kv[0] not in profile.allergens, kv[0]))
    ]

    low = [by_key[k] for k in GAP_NUTRIENTS if by_key[k]["status"] == "low"]
    low.sort(key=lambda r: r["pct_of_share"])
    gaps = []
    for row in low[:4]:
        sugg = suggestions_for(row["key"], profile.diets, profile.allergens, profile.cuisines)
        if sugg:
            gaps.append({**sugg, "amount": row["amount"], "pct_daily": row["pct_daily"],
                         "pct_of_share": row["pct_of_share"], "daily_target": row["daily_target"]})

    warnings = [
        f"High in {r['label'].lower()}: {r['amount']:g} {r['unit']} is {r['pct_daily']}% of your daily limit."
        for r in rows if r["kind"] == "limit" and r["status"] == "high"
    ]

    return {
        "scope": scope,
        "items": scaled_items,
        "totals": totals,
        "targets": {k: round(v, 1) for k, v in targets.items()},
        "nutrients": rows,
        "macro_split": macro_split,
        "allergens": allergens,
        "allergen_conflicts": [a["label"] for a in allergens if a["conflict"]],
        "gaps": gaps,
        "warnings": warnings,
    }
