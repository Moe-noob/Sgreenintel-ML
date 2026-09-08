"""
Static, non-AI reference data: species baseline care requirements and
disease management guidance.

This is deliberately NOT model output — it's a lookup table attached
*after* CNN classification (Feature 1) and reused for weather-based
alerts (Feature 3). Framing this as a knowledge base, not AI-derived
information, is intentional and should stay consistent throughout the
report and defense.

Sources (species baseline care):
Colorado State University Extension, NC State Extension, Penn State
Extension, Oklahoma State University Extension, University of Minnesota
Extension, University of Illinois Extension, Oregon State University
Extension, Texas A&M AgriLife Extension.

Sources (disease management):
NC State Extension, UMass Amherst Center for Agriculture, University of
Minnesota Extension, University of Illinois Extension, University of
Kentucky Cooperative Extension.
"""

# ---------------------------------------------------------------------------
# Species baseline care requirements (applies regardless of health status)
# ---------------------------------------------------------------------------

SPECIES_PROFILES = {
    "Apple": {
        "day_temp_c": "18-24",
        "night_temp_c": "above -2 (fruit damage risk below this)",
        "ideal_temp_range_c": (18, 24),
        "watering": "Young trees: deep watering weekly. Mature trees: less frequent, water when top few inches of soil are dry.",
        "sun": "Full sun",
    },
    "Corn_(maize)": {
        "day_temp_c": "25-30 (heat stress above 29)",
        "night_temp_c": "above 10 (cold stress below this)",
        "ideal_temp_range_c": (25, 29),
        "watering": "~25mm (1 inch) per week",
        "sun": "Full sun",
    },
    "Grape": {
        "day_temp_c": "25-32 (overall optimum growth range)",
        "night_temp_c": "—",
        "ideal_temp_range_c": (25, 32),
        "watering": "New vines: 25mm every 7-10 days. Mature vines: 25mm every 2-3 weeks — mature vines are drought-tolerant and easily overwatered.",
        "sun": "Full sun",
    },
    "Pepper,_bell": {
        "day_temp_c": "21-29",
        "night_temp_c": "15-21",
        "ideal_temp_range_c": (21, 29),
        "watering": "Keep soil evenly moist — avoid dry/wet swings, which cause blossom end rot",
        "sun": "Full sun, 6-8 hrs/day",
    },
    "Potato": {
        "day_temp_c": "Cool-season crop; soil temp 16-21 optimal for tuber formation",
        "night_temp_c": "—",
        "ideal_temp_range_c": (16, 21),
        "watering": "~25mm (1 inch) per week; more often in sandy soil",
        "sun": "Full sun",
    },
    "Tomato": {
        "day_temp_c": "21-27",
        "night_temp_c": "15-21",
        "ideal_temp_range_c": (21, 27),
        "watering": "Deep watering every 3-7 days depending on conditions",
        "sun": "Full sun, 6-8 hrs/day",
    },
}


# ---------------------------------------------------------------------------
# Disease category management guidance
# Category-level, not per-disease — most diseases within a category share
# the same management logic, so this avoids padding 27 near-duplicate texts.
# ---------------------------------------------------------------------------

DISEASE_CATEGORIES = {
    "healthy": {
        "label": "Healthy",
        "management": "No treatment needed. Continue standard care per species profile.",
    },
    "fungal": {
        "label": "Fungal disease",
        "management": (
            "Remove and destroy infected leaves/debris (do not compost). "
            "Avoid overhead watering — wet foliage spreads fungal spores; water at soil level instead. "
            "Improve air circulation through proper spacing/pruning. "
            "Practice crop rotation where applicable. "
            "Fungicide treatment may help in active outbreaks — consult local agricultural extension guidance for approved products."
        ),
    },
    "bacterial": {
        "label": "Bacterial disease",
        "management": (
            "Remove and destroy infected plant material. "
            "Avoid working around plants while foliage is wet — this spreads bacteria. "
            "Avoid overhead watering. "
            "Copper-based treatments may help reduce spread — consult local agricultural extension guidance."
        ),
    },
    "viral": {
        "label": "Viral disease — no cure available",
        "management": (
            "There is no cure once a plant is infected. Management is prevention-focused: "
            "remove and destroy the infected plant to prevent spread. "
            "Control insect vectors (e.g. whiteflies, aphids) that transmit the virus between plants. "
            "Wash hands/tools after handling infected plants before touching healthy ones. "
            "Consider resistant varieties for future planting."
        ),
    },
    "rust": {
        "label": "Rust (fungal)",
        "management": (
            "Remove infected leaves where feasible. "
            "Where relevant, remove nearby alternate host plants that allow the rust fungus to complete its life cycle. "
            "Fungicide treatment may help — consult local agricultural extension guidance. "
            "Resistant varieties reduce susceptibility in future planting."
        ),
    },
    "pest": {
        "label": "Pest infestation",
        "management": (
            "Increase humidity around the plant — dry conditions favor mite/pest outbreaks. "
            "Insecticidal soap or miticide treatment may help — consult local agricultural extension guidance. "
            "Introducing natural predators (e.g. predatory mites) is an option in larger growing setups."
        ),
    },
}


# ---------------------------------------------------------------------------
# Maps each of the 27 PlantVillage class names (exact folder names, since
# that's what the CNN's class_names list contains) to its crop, condition,
# category, and any disease-specific note.
# ---------------------------------------------------------------------------

CLASS_INFO = {
    "Apple___Apple_scab": {
        "crop": "Apple", "condition": "Apple scab", "category": "fungal",
        "note": None,
    },
    "Apple___Black_rot": {
        "crop": "Apple", "condition": "Black rot", "category": "fungal",
        "note": None,
    },
    "Apple___Cedar_apple_rust": {
        "crop": "Apple", "condition": "Cedar apple rust", "category": "rust",
        "note": "Alternate host is Eastern red cedar/juniper — removing nearby junipers can help break the disease cycle.",
    },
    "Apple___healthy": {
        "crop": "Apple", "condition": "Healthy", "category": "healthy", "note": None,
    },

    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": {
        "crop": "Corn_(maize)", "condition": "Cercospora leaf spot / Gray leaf spot", "category": "fungal",
        "note": None,
    },
    "Corn_(maize)___Common_rust_": {
        "crop": "Corn_(maize)", "condition": "Common rust", "category": "rust",
        "note": None,
    },
    "Corn_(maize)___Northern_Leaf_Blight": {
        "crop": "Corn_(maize)", "condition": "Northern Leaf Blight", "category": "fungal",
        "note": "Visually similar to Gray leaf spot — if uncertain, treat as general fungal management applies to both.",
    },
    "Corn_(maize)___healthy": {
        "crop": "Corn_(maize)", "condition": "Healthy", "category": "healthy", "note": None,
    },

    "Grape___Black_rot": {
        "crop": "Grape", "condition": "Black rot", "category": "fungal", "note": None,
    },
    "Grape___Esca_(Black_Measles)": {
        "crop": "Grape", "condition": "Esca (Black Measles)", "category": "fungal",
        "note": "A wood-infecting disease — pruning out infected wood is important in addition to general fungal management.",
    },
    "Grape___healthy": {
        "crop": "Grape", "condition": "Healthy", "category": "healthy", "note": None,
    },
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": {
        "crop": "Grape", "condition": "Leaf blight (Isariopsis Leaf Spot)", "category": "fungal", "note": None,
    },

    "Pepper,_bell___Bacterial_spot": {
        "crop": "Pepper,_bell", "condition": "Bacterial spot", "category": "bacterial", "note": None,
    },
    "Pepper,_bell___healthy": {
        "crop": "Pepper,_bell", "condition": "Healthy", "category": "healthy", "note": None,
    },

    "Potato___Early_blight": {
        "crop": "Potato", "condition": "Early blight", "category": "fungal", "note": None,
    },
    "Potato___healthy": {
        "crop": "Potato", "condition": "Healthy", "category": "healthy", "note": None,
    },
    "Potato___Late_blight": {
        "crop": "Potato", "condition": "Late blight", "category": "fungal",
        "note": "Spreads faster than early blight — remove infected material promptly.",
    },

    "Tomato___Bacterial_spot": {
        "crop": "Tomato", "condition": "Bacterial spot", "category": "bacterial", "note": None,
    },
    "Tomato___Early_blight": {
        "crop": "Tomato", "condition": "Early blight", "category": "fungal", "note": None,
    },
    "Tomato___healthy": {
        "crop": "Tomato", "condition": "Healthy", "category": "healthy", "note": None,
    },
    "Tomato___Late_blight": {
        "crop": "Tomato", "condition": "Late blight", "category": "fungal",
        "note": "Spreads rapidly and can affect fruit — remove infected material promptly.",
    },
    "Tomato___Leaf_Mold": {
        "crop": "Tomato", "condition": "Leaf Mold", "category": "fungal",
        "note": "Favored by high humidity — improving ventilation is especially important.",
    },
    "Tomato___Septoria_leaf_spot": {
        "crop": "Tomato", "condition": "Septoria leaf spot", "category": "fungal", "note": None,
    },
    "Tomato___Spider_mites Two-spotted_spider_mite": {
        "crop": "Tomato", "condition": "Two-spotted spider mite", "category": "pest", "note": None,
    },
    "Tomato___Target_Spot": {
        "crop": "Tomato", "condition": "Target Spot", "category": "fungal", "note": None,
    },
    "Tomato___Tomato_mosaic_virus": {
        "crop": "Tomato", "condition": "Tomato mosaic virus", "category": "viral",
        "note": "Spreads easily by contact (hands, tools, clothing) — avoid handling healthy plants after touching infected ones.",
    },
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {
        "crop": "Tomato", "condition": "Tomato Yellow Leaf Curl Virus", "category": "viral",
        "note": "Transmitted by whiteflies — controlling the whitefly population is the primary prevention method.",
    },
}


def get_care_info(class_name: str) -> dict:
    """
    Given a class name exactly as produced by the CNN (e.g.
    'Tomato___Early_blight'), returns combined species baseline care +
    disease category management + any disease-specific note.
    """
    if class_name not in CLASS_INFO:
        raise ValueError(f"Unknown class name: {class_name}")

    info = CLASS_INFO[class_name]
    species_profile = SPECIES_PROFILES[info["crop"]]
    category_info = DISEASE_CATEGORIES[info["category"]]

    return {
        "crop": info["crop"].replace("_", " ").replace("(maize)", "(Maize)"),
        "condition": info["condition"],
        "category_label": category_info["label"],
        "management": category_info["management"],
        "specific_note": info["note"],
        "baseline_care": species_profile,
    }