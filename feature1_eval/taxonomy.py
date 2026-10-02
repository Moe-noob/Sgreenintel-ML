"""
Unified class taxonomy for the Feature 1 evaluation kit: crop -> condition.

Every dataset uses its own label names ("Tomato___Late_blight",
"Tomato leaf late blight", "tomato late blight" ...). This module maps
them all onto one label set:

    label = "<crop>__<condition>"          e.g. "tomato__late_blight"

so data from different sources can be merged, the crop can be read off
any label (crop selector, Feature 2 link), and the benchmark compares
like with like.

Special labels
  UNSUPPORTED  leaves of crops this app does not cover (banana, rice, ...),
               used to train/calibrate the "not a supported leaf" output.
  None         a source label that is deliberately excluded (e.g. carrot
               cavity spot is a ROOT disease, with no healthy carrot class).

Which classes are finally trained is decided from the data (data/splits.py):
a class enters only with enough real-field images (see config.py).
"""

UNSUPPORTED = "_unsupported"

# crop key -> (English, Arabic, Feature 2 crop keys it corresponds to)
CROPS = {
    "apple":       ("Apple", "تفاح", []),
    "bean":        ("Green bean", "فاصوليا", ["Beans, green"]),
    "bell_pepper": ("Bell pepper", "فلفل رومي", ["Sweet peppers {bell}"]),
    "broccoli":    ("Broccoli", "بروكلي", ["Broccoli"]),
    "cabbage":     ("Cabbage", "ملفوف", ["Cabbage"]),
    "cauliflower": ("Cauliflower", "قرنبيط", ["Cauliflower"]),
    "corn":        ("Corn (maize)", "ذرة", ["Sweet corn"]),
    "cucumber":    ("Cucumber", "خيار", ["Cucumber {Fresh Market}"]),
    "eggplant":    ("Eggplant", "باذنجان", ["EggPlant"]),
    "garlic":      ("Garlic", "ثوم", ["Garlic"]),
    "grape":       ("Grape", "عنب", []),
    "lettuce":     ("Lettuce", "خس", ["Lettuce"]),
    "melon":       ("Melon / watermelon", "شمام / بطيخ", ["Sweet Melons", "Watermelon"]),
    "okra":        ("Okra", "بامية", ["Okra"]),
    "onion":       ("Onion", "بصل", ["Onions {dry}"]),
    "potato":      ("Potato", "بطاطس", ["Potato"]),
    "squash":      ("Squash / zucchini", "كوسة", ["Squash", "Pumpkin"]),
    "strawberry":  ("Strawberry", "فراولة", []),
    "tomato":      ("Tomato", "طماطم", ["Tomato"]),
}

# condition key -> (English, Arabic)
CONDITIONS = {
    "healthy": ("Healthy", "سليم"),
    "alternaria_leaf_spot": ("Alternaria leaf spot", "تبقع الأوراق الألترناري"),
    "angular_leaf_spot": ("Angular leaf spot", "التبقع الزاوي"),
    "anthracnose": ("Anthracnose", "الأنثراكنوز"),
    "bacterial_spot": ("Bacterial spot", "التبقع البكتيري"),
    "bacterial_wilt": ("Bacterial wilt", "الذبول البكتيري"),
    "black_rot": ("Black rot", "العفن الأسود"),
    "cedar_apple_rust": ("Cedar apple rust", "صدأ التفاح"),
    "cercospora_leaf_spot": ("Cercospora leaf spot", "تبقع الأوراق السركسبوري"),
    "common_rust": ("Common rust", "الصدأ العادي"),
    "corn_smut": ("Common smut", "التفحم"),
    "downy_mildew": ("Downy mildew", "البياض الزغبي"),
    "early_blight": ("Early blight", "اللفحة المبكرة"),
    "esca": ("Esca (black measles)", "مرض الإسكا"),
    "frog_eye_leaf_spot": ("Frog-eye leaf spot", "تبقع عين الضفدع"),
    "gray_leaf_spot": ("Gray leaf spot", "التبقع الرمادي"),
    "halo_blight": ("Halo blight", "اللفحة الهالية"),
    "isariopsis_leaf_spot": ("Leaf blight (Isariopsis)", "لفحة الأوراق"),
    "late_blight": ("Late blight", "اللفحة المتأخرة"),
    "leaf_blight": ("Leaf blight", "لفحة الأوراق"),
    "leaf_curl_virus": ("Yellow leaf curl virus", "فيروس تجعد واصفرار الأوراق"),
    "leaf_mold": ("Leaf mold", "عفن الأوراق"),
    "leaf_scorch": ("Leaf scorch", "احتراق الأوراق"),
    "leaf_spot": ("Leaf spot", "تبقع الأوراق"),
    "leafroll_virus": ("Leafroll disease", "مرض التفاف الأوراق"),
    "mosaic_virus": ("Mosaic virus", "فيروس الموزاييك"),
    "northern_leaf_blight": ("Northern leaf blight", "اللفحة الشمالية"),
    "northern_leaf_spot": ("Northern leaf spot", "التبقع الشمالي"),
    "powdery_mildew": ("Powdery mildew", "البياض الدقيقي"),
    "purple_blotch": ("Purple blotch", "اللطخة الأرجوانية"),
    "rust": ("Rust", "الصدأ"),
    "scab": ("Scab", "الجرب"),
    "septoria_leaf_spot": ("Septoria leaf spot", "تبقع الأوراق السبتوري"),
    "spider_mites": ("Spider mites", "العنكبوت الأحمر"),
    "target_spot": ("Target spot", "التبقع الهدفي"),
    "yellow_mosaic_virus": ("Zucchini yellow mosaic virus", "فيروس موزاييك الكوسة الأصفر"),
    "yellow_vein_mosaic_virus": ("Yellow vein mosaic virus", "فيروس موزاييك العروق الصفراء"),
}


def label(crop, condition):
    assert crop in CROPS, crop
    assert condition in CONDITIONS, condition
    return f"{crop}__{condition}"


def crop_of(lbl):
    return None if lbl in (None, UNSUPPORTED) else lbl.split("__", 1)[0]


def condition_of(lbl):
    return None if lbl in (None, UNSUPPORTED) else lbl.split("__", 1)[1]


def display(lbl, lang="en"):
    if lbl == UNSUPPORTED:
        return "Unsupported plant" if lang == "en" else "نبات غير مدعوم"
    c, d = lbl.split("__", 1)
    i = 0 if lang == "en" else 1
    return f"{CROPS[c][i]} — {CONDITIONS[d][i]}"


def crop_from_feature2(feature2_key):
    """Feature 2 crop key (e.g. 'Sweet peppers {bell}') -> crop key here, or None."""
    for k, (_, _, f2) in CROPS.items():
        if feature2_key in f2:
            return k
    return None


L = label

# ---------------------------------------------------------------------------
# Source label maps
# ---------------------------------------------------------------------------

# v1's 35 classes (PlantVillage + fgvc8 + cds + sms naming, data/processed_v2)
LEGACY_35 = {
    "Apple___Apple_scab": L("apple", "scab"),
    "Apple___Black_rot": L("apple", "black_rot"),
    "Apple___Cedar_apple_rust": L("apple", "cedar_apple_rust"),
    "Apple___Frog_eye_leaf_spot": L("apple", "frog_eye_leaf_spot"),
    "Apple___Powdery_mildew": L("apple", "powdery_mildew"),
    "Apple___healthy": L("apple", "healthy"),
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": L("corn", "gray_leaf_spot"),
    "Corn_(maize)___Common_rust_": L("corn", "common_rust"),
    "Corn_(maize)___Northern_Leaf_Blight": L("corn", "northern_leaf_blight"),
    "Corn_(maize)___Northern_Leaf_Spot": L("corn", "northern_leaf_spot"),
    "Corn_(maize)___healthy": L("corn", "healthy"),
    "Grape___Black_rot": L("grape", "black_rot"),
    "Grape___Esca_(Black_Measles)": L("grape", "esca"),
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": L("grape", "isariopsis_leaf_spot"),
    "Grape___healthy": L("grape", "healthy"),
    "Pepper,_bell___Bacterial_spot": L("bell_pepper", "bacterial_spot"),
    "Pepper,_bell___healthy": L("bell_pepper", "healthy"),
    "Potato___Early_blight": L("potato", "early_blight"),
    "Potato___Late_blight": L("potato", "late_blight"),
    "Potato___healthy": L("potato", "healthy"),
    "Strawberry___Angular_leafspot": L("strawberry", "angular_leaf_spot"),
    "Strawberry___Leaf_scorch": L("strawberry", "leaf_scorch"),
    "Strawberry___Leaf_spot": L("strawberry", "leaf_spot"),
    "Strawberry___Powdery_mildew": L("strawberry", "powdery_mildew"),
    "Strawberry___healthy": L("strawberry", "healthy"),
    "Tomato___Bacterial_spot": L("tomato", "bacterial_spot"),
    "Tomato___Early_blight": L("tomato", "early_blight"),
    "Tomato___Late_blight": L("tomato", "late_blight"),
    "Tomato___Leaf_Mold": L("tomato", "leaf_mold"),
    "Tomato___Septoria_leaf_spot": L("tomato", "septoria_leaf_spot"),
    "Tomato___Spider_mites Two-spotted_spider_mite": L("tomato", "spider_mites"),
    "Tomato___Target_Spot": L("tomato", "target_spot"),
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": L("tomato", "leaf_curl_virus"),
    "Tomato___Tomato_mosaic_virus": L("tomato", "mosaic_virus"),
    "Tomato___healthy": L("tomato", "healthy"),
}

# PlantDoc (Singh et al. 2020), 27 folder names (train/ and test/)
PLANTDOC = {
    "Apple Scab Leaf": L("apple", "scab"),
    "Apple leaf": L("apple", "healthy"),
    "Apple rust leaf": L("apple", "cedar_apple_rust"),
    "Bell_pepper leaf": L("bell_pepper", "healthy"),
    "Bell_pepper leaf spot": L("bell_pepper", "bacterial_spot"),
    "Blueberry leaf": UNSUPPORTED,
    "Cherry leaf": UNSUPPORTED,
    "Corn Gray leaf spot": L("corn", "gray_leaf_spot"),
    "Corn leaf blight": L("corn", "northern_leaf_blight"),
    "Corn rust leaf": L("corn", "common_rust"),
    "Peach leaf": UNSUPPORTED,
    "Potato leaf early blight": L("potato", "early_blight"),
    "Potato leaf late blight": L("potato", "late_blight"),
    "Raspberry leaf": UNSUPPORTED,
    "Soyabean leaf": UNSUPPORTED,
    "Squash Powdery mildew leaf": L("squash", "powdery_mildew"),
    "Strawberry leaf": L("strawberry", "healthy"),
    "Tomato Early blight leaf": L("tomato", "early_blight"),
    "Tomato Septoria leaf spot": L("tomato", "septoria_leaf_spot"),
    "Tomato leaf": L("tomato", "healthy"),
    "Tomato leaf bacterial spot": L("tomato", "bacterial_spot"),
    "Tomato leaf late blight": L("tomato", "late_blight"),
    "Tomato leaf mosaic virus": L("tomato", "mosaic_virus"),
    "Tomato leaf yellow virus": L("tomato", "leaf_curl_virus"),
    "Tomato mold leaf": L("tomato", "leaf_mold"),
    # Two folders PlantDoc also ships (not in its classification prompt list):
    "Tomato two spotted spider mites leaf": L("tomato", "spider_mites"),
    "grape leaf": L("grape", "healthy"),
    "grape leaf black rot": L("grape", "black_rot"),
}

# PlantWild v1 (Wei et al. 2024), 89 classes (+3 names seen in the 92-class variant),
# names as in github.com/tqwei05/MVPDR gpt_files_plt44/plantwild_prompts_50_*.json
_U = UNSUPPORTED
PLANTWILD = {
    "apple black rot": L("apple", "black_rot"),
    "apple leaf": L("apple", "healthy"),
    "apple mosaic virus": L("apple", "mosaic_virus"),
    "apple rust": L("apple", "cedar_apple_rust"),
    "apple scab": L("apple", "scab"),
    "banana leaf": _U, "banana panama disease": _U,
    "basil downy mildew": _U, "basil leaf": _U,
    "bean halo blight": L("bean", "halo_blight"),
    "bean leaf": L("bean", "healthy"),
    "bean mosaic virus": L("bean", "mosaic_virus"),
    "bean rust": L("bean", "rust"),
    "bell pepper leaf": L("bell_pepper", "healthy"),
    "bell pepper leaf spot": L("bell_pepper", "bacterial_spot"),
    "blueberry leaf": _U, "blueberry rust": _U,
    "broccoli downy mildew": L("broccoli", "downy_mildew"),
    "broccoli leaf": L("broccoli", "healthy"),
    "cabbage alternaria leaf spot": L("cabbage", "alternaria_leaf_spot"),
    "cabbage leaf": L("cabbage", "healthy"),
    "carrot cavity spot": None,      # root disease; no healthy carrot class in the dataset
    "cauliflower alternaria leaf spot": L("cauliflower", "alternaria_leaf_spot"),
    "cauliflower leaf": L("cauliflower", "healthy"),
    "celery anthracnose": _U, "celery early blight": _U, "celery late blight": _U, "celery leaf": _U,
    "cherry leaf": _U, "cherry leaf spot": _U, "cherry powdery mildew": _U,
    "citrus canker": _U, "citrus greening disease": _U,
    "coffee leaf": _U, "coffee leaf rust": _U,
    "corn gray leaf spot": L("corn", "gray_leaf_spot"),
    "corn leaf": L("corn", "healthy"),
    "corn northern leaf blight": L("corn", "northern_leaf_blight"),
    "corn rust": L("corn", "common_rust"),
    "corn smut": L("corn", "corn_smut"),
    "cucumber angular leaf spot": L("cucumber", "angular_leaf_spot"),
    "cucumber bacterial wilt": L("cucumber", "bacterial_wilt"),
    "cucumber leaf": L("cucumber", "healthy"),
    "cucumber powdery mildew": L("cucumber", "powdery_mildew"),
    "eggplant cercospora leaf spot": L("eggplant", "cercospora_leaf_spot"),
    "eggplant leaf": L("eggplant", "healthy"),
    "garlic leaf": L("garlic", "healthy"),
    "garlic leaf blight": L("garlic", "leaf_blight"),
    "garlic rust": L("garlic", "rust"),
    "ginger leaf": _U, "ginger leaf spot": _U, "ginger sheath blight": _U,
    "grape black rot": L("grape", "black_rot"),
    "grape downy mildew": L("grape", "downy_mildew"),
    "grape leaf": L("grape", "healthy"),
    "grape leaf spot": L("grape", "leaf_spot"),
    "grapevine leafroll disease": L("grape", "leafroll_virus"),
    "lettuce downy mildew": L("lettuce", "downy_mildew"),
    "lettuce leaf": L("lettuce", "healthy"),
    "lettuce mosaic virus": L("lettuce", "mosaic_virus"),
    "maple leaf": _U, "maple tar spot": _U,
    "peach leaf": _U, "peach leaf curl": _U,
    "plum leaf": _U, "plum leaf spot": _U, "plum pocket disease": _U,
    "potato early blight": L("potato", "early_blight"),
    "potato late blight": L("potato", "late_blight"),
    "potato leaf": L("potato", "healthy"),
    "raspberry leaf": _U,
    "rice blast": _U, "rice leaf": _U, "rice sheath blight": _U,
    "soybean leaf": _U,
    "squash leaf": L("squash", "healthy"),
    "squash powdery mildew": L("squash", "powdery_mildew"),
    "strawberry anthracnose": L("strawberry", "anthracnose"),
    "strawberry leaf": L("strawberry", "healthy"),
    "strawberry leaf scorch": L("strawberry", "leaf_scorch"),
    "tobacco leaf": _U, "tobacco mosaic virus": _U,
    "tomato bacterial leaf spot": L("tomato", "bacterial_spot"),
    "tomato early blight": L("tomato", "early_blight"),
    "tomato late blight": L("tomato", "late_blight"),
    "tomato leaf": L("tomato", "healthy"),
    "tomato leaf mold": L("tomato", "leaf_mold"),
    "tomato mosaic virus": L("tomato", "mosaic_virus"),
    "tomato septoria leaf spot": L("tomato", "septoria_leaf_spot"),
    "tomato yellow leaf curl virus": L("tomato", "leaf_curl_virus"),
    "zucchini leaf": L("squash", "healthy"),
    "zucchini yellow mosaic virus": L("squash", "yellow_mosaic_virus"),
}

SOURCE_MAPS = {"legacy35": LEGACY_35, "plantdoc": PLANTDOC, "plantwild": PLANTWILD}


def normalise(name):
    return " ".join(str(name).replace("_", " ").replace("-", " ").lower().split())


def unify(map_name_or_dict, raw_label):
    """
    Map a source label to a unified label. Returns (label_or_None, known: bool).
    Matching tolerates case/underscore/space differences. Unknown labels return
    (None, False) so the manifest builder can report them for manual mapping.
    """
    table = SOURCE_MAPS[map_name_or_dict] if isinstance(map_name_or_dict, str) else map_name_or_dict
    if raw_label in table:
        return table[raw_label], True
    n = normalise(raw_label)
    for k, v in table.items():
        if normalise(k) == n:
            return v, True
    return None, False


def all_labels():
    """Every unified label reachable from the built-in source maps (plus UNSUPPORTED)."""
    out = set()
    for t in SOURCE_MAPS.values():
        out.update(v for v in t.values() if v)
    return sorted(out)
