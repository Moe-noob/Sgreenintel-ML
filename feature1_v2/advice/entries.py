"""
Per-condition knowledge base entries (one per taxonomy label).

Each entry
  category   management template in categories.py
  cause      causal organism (scientific name)
  symptoms   what to look for to CONFIRM the diagnosis (EN / AR)
  key_sign   the one sign that best separates it from its look-alikes
             (used by the look-alike helper when two predictions are close)
  lookalikes labels commonly confused with it
  note       disease-specific advice that overrides / adds to the template
  weather    id of a published weather-risk rule (weather_risk.py), if any
  sources    keys into sources.py (symptom and management references)

Symptom descriptions are condensed from the cited compendia / extension
guidelines and are marked as drafts for expert review (kb.REVIEW_STATUS).
"""


def E(category, cause, symptoms, key_sign, lookalikes=(), sources=(), note=None, weather=None):
    return {"category": category, "cause": cause,
            "symptoms": {"en": symptoms[0], "ar": symptoms[1]},
            "key_sign": {"en": key_sign[0], "ar": key_sign[1]},
            "lookalikes": list(lookalikes), "sources": list(sources),
            "note": {"en": note[0], "ar": note[1]} if note else None, "weather": weather}


H = lambda crop_sources: E("healthy", None,
                            ("Leaves are evenly coloured with no spots, powder, mosaic or curling.",
                             "الأوراق متجانسة اللون بلا بقع أو مسحوق أو تبرقش أو تجعد."),
                            ("No lesions or abnormal colour patterns.", "لا توجد بقع أو أنماط لونية غير طبيعية."),
                            sources=crop_sources)

ENTRIES = {
    # ------------------------------------------------------------------ tomato
    "tomato__healthy": H(["ucipm_tomato"]),
    "tomato__early_blight": E(
        "fungal_leaf_spot", "Alternaria linariae (A. solani)",
        ("Brown spots up to about 1-2 cm with concentric rings ('target' pattern), often with a yellow halo; starts on the OLDEST, lowest leaves and moves up.",
         "بقع بنية حتى 1-2 سم تقريبًا بحلقات متداخلة (شكل الهدف)، غالبًا مع هالة صفراء؛ تبدأ على الأوراق الأقدم والسفلية ثم تصعد."),
        ("Dark concentric rings inside dry brown spots on lower leaves.", "حلقات داكنة متداخلة داخل بقع بنية جافة على الأوراق السفلية."),
        ["tomato__target_spot", "tomato__septoria_leaf_spot", "tomato__late_blight"], ["aps_tomato", "ucipm_tomato"]),
    "tomato__late_blight": E(
        "oomycete", "Phytophthora infestans",
        ("Large, irregular, greasy grey-green to dark-brown patches that grow fast; in humid mornings a white downy growth appears at the lesion edge on the leaf underside. Stems and green fruit get firm brown patches.",
         "بقع كبيرة غير منتظمة دهنية المظهر رمادية مخضرة إلى بنية داكنة تتسع بسرعة؛ وفي الصباح الرطب يظهر نمو أبيض زغبي على حافة البقعة في الوجه السفلي. وتظهر على السيقان والثمار الخضراء بقع بنية صلبة."),
        ("Fast-growing water-soaked patches, no rings, white growth on the underside in humid conditions.", "بقع مائية سريعة الاتساع بلا حلقات، مع نمو أبيض على الوجه السفلي في الرطوبة."),
        ["tomato__early_blight", "tomato__leaf_mold"], ["aps_tomato", "ucipm_tomato"],
        note=("Late blight is the most destructive tomato disease in cool humid spells (in Saudi Arabia mainly winter greenhouses and the south-western highlands). Treat neighbouring tomato and potato plants as at risk.",
              "اللفحة المتأخرة أخطر أمراض الطماطم في الفترات الباردة الرطبة (في المملكة غالبًا في البيوت المحمية شتاءً وفي المرتفعات الجنوبية الغربية). اعتبر نباتات الطماطم والبطاطس المجاورة معرّضة للخطر."),
        weather="hutton_late_blight"),
    "tomato__septoria_leaf_spot": E(
        "fungal_leaf_spot", "Septoria lycopersici",
        ("Many small (about 2-5 mm) round spots with a grey-white centre and dark border, with tiny black dots (fruiting bodies) in the centre; lower leaves first.",
         "بقع صغيرة كثيرة (حوالي 2-5 مم) دائرية بمركز رمادي مبيض وحافة داكنة، وفي مركزها نقاط سوداء دقيقة (أجسام ثمرية)؛ تبدأ على الأوراق السفلية."),
        ("Small spots with pale centres containing black pin-point dots.", "بقع صغيرة بمراكز فاتحة تحوي نقاطًا سوداء دقيقة."),
        ["tomato__early_blight", "tomato__bacterial_spot"], ["aps_tomato", "ucipm_tomato"]),
    "tomato__bacterial_spot": E(
        "bacterial", "Xanthomonas spp. (X. euvesicatoria, X. perforans, X. vesicatoria, X. gardneri)",
        ("Small (1-3 mm), dark, greasy-looking spots, sometimes with a yellow halo; spots may merge and leaf edges scorch. Raised scabby spots on fruit.",
         "بقع صغيرة (1-3 مم) داكنة دهنية المظهر، أحيانًا مع هالة صفراء؛ قد تندمج البقع وتحترق حواف الورقة. وتظهر على الثمار بقع بارزة متقشرة."),
        ("Tiny dark greasy spots with no rings and no black dots inside.", "بقع داكنة دهنية صغيرة جدًا بلا حلقات ولا نقاط سوداء داخلها."),
        ["tomato__septoria_leaf_spot", "tomato__target_spot"], ["aps_tomato", "ucipm_tomato"]),
    "tomato__target_spot": E(
        "fungal_leaf_spot", "Corynespora cassiicola",
        ("Brown spots with light-brown centres and faint concentric rings, often with a yellow margin; can spread to fruit as small sunken spots.",
         "بقع بنية بمراكز فاتحة وحلقات متداخلة خفيفة، غالبًا مع حافة صفراء؛ وقد تنتقل إلى الثمار كبقع صغيرة غائرة."),
        ("Rings are fainter and spots smaller than early blight; centre may crack.", "الحلقات أخف والبقع أصغر من اللفحة المبكرة؛ وقد يتشقق مركز البقعة."),
        ["tomato__early_blight", "tomato__bacterial_spot"], ["aps_tomato"]),
    "tomato__leaf_mold": E(
        "fungal_leaf_spot", "Passalora fulva (Cladosporium fulvum)",
        ("Pale yellow patches on the UPPER leaf surface with olive-green to brown velvety mould directly beneath on the underside; mainly in humid greenhouses.",
         "بقع صفراء باهتة على الوجه العلوي للورقة يقابلها تحتها على الوجه السفلي عفن مخملي زيتوني إلى بني؛ غالبًا في البيوت المحمية الرطبة."),
        ("Olive-green velvety mould under yellow patches.", "عفن مخملي زيتوني تحت البقع الصفراء."),
        ["tomato__late_blight"], ["aps_tomato", "fao_gap_greenhouse"],
        note=("Leaf mold is controlled mainly by lowering greenhouse humidity (below about 85 %): ventilation, heating at dawn, wider spacing.",
              "يُكافح عفن الأوراق أساسًا بخفض رطوبة البيت المحمي (أقل من 85٪ تقريبًا): التهوية، والتدفئة عند الفجر، وتوسيع المسافات.")),
    "tomato__leaf_curl_virus": E(
        "virus_whitefly", "Tomato yellow leaf curl virus (TYLCV, begomovirus)",
        ("New leaves small, cupped upward, with yellow margins; plants stunted and bushy; flowers drop and fruit set falls sharply.",
         "الأوراق الحديثة صغيرة ملتفة للأعلى بحواف صفراء؛ النبات متقزم كثيف؛ تتساقط الأزهار ويقل العقد بشدة."),
        ("Upward-cupped small new leaves with yellow edges, whiteflies present.", "أوراق حديثة صغيرة ملتفة للأعلى بحواف صفراء مع وجود الذباب الأبيض."),
        ["tomato__mosaic_virus", "tomato__spider_mites"], ["aps_tomato", "ucipm_tomato"],
        note=("TYLCV is one of the main tomato problems in Saudi Arabia; whitefly control and resistant varieties are the key measures.",
              "فيروس تجعد واصفرار أوراق الطماطم من أهم مشكلات الطماطم في المملكة؛ ومكافحة الذباب الأبيض والأصناف المقاومة هي الإجراءات الأساسية.")),
    "tomato__mosaic_virus": E(
        "virus_contact", "Tomato mosaic virus / tobacco mosaic virus (tobamoviruses)",
        ("Light- and dark-green mottling (mosaic) of leaves, sometimes fern-like narrow leaves and distortion; uneven fruit ripening.",
         "تبرقش الأوراق بالأخضر الفاتح والداكن (موزاييك)، أحيانًا أوراق ضيقة تشبه السرخس وتشوه؛ ونضج غير منتظم للثمار."),
        ("Patchy light/dark green mosaic without upward cupping.", "تبرقش أخضر فاتح وداكن دون التفاف للأعلى."),
        ["tomato__leaf_curl_virus", "tomato__spider_mites"], ["aps_tomato", "ucipm_tomato"],
        note=("Check also for Tomato brown rugose fruit virus (ToBRFV), a tobamovirus that breaks Tm-2² resistance and is a regulated pest in many countries: report suspected cases to MEWA.",
              "تحقّق أيضًا من فيروس تبرقش ثمار الطماطم البني (ToBRFV)، وهو من التوباموفيرس ويكسر مقاومة الجين Tm-2² وآفة خاضعة للتنظيم في دول كثيرة: أبلغ الوزارة عن الحالات المشتبه بها.")),
    "tomato__spider_mites": E(
        "mites", "Tetranychus urticae (two-spotted spider mite)",
        ("Fine pale stippling (tiny dots) on the upper leaf surface, bronzing or yellowing, and fine webbing on the underside in heavy infestations.",
         "تنقيط باهت دقيق على الوجه العلوي للورقة، مع اصفرار أو لون برونزي، ونسيج رفيع على الوجه السفلي في الإصابات الشديدة."),
        ("Fine stippling plus webbing and moving mites under a lens.", "تنقيط دقيق مع نسيج وحَلَم متحرك تحت العدسة."),
        ["tomato__mosaic_virus", "tomato__leaf_curl_virus"], ["aps_tomato", "ucipm_tomato", "irac"]),
    # ------------------------------------------------------------------ potato
    "potato__healthy": H(["ucipm_potato"]),
    "potato__early_blight": E(
        "fungal_leaf_spot", "Alternaria solani",
        ("Dark-brown spots with concentric rings, limited by leaf veins (angular), on older leaves first; more common late in the season and on stressed plants.",
         "بقع بنية داكنة بحلقات متداخلة، تحدها عروق الورقة (زاوية الشكل)، على الأوراق الأقدم أولًا؛ أكثر شيوعًا في آخر الموسم وعلى النباتات المجهدة."),
        ("Dry dark spots with concentric rings, limited by veins.", "بقع جافة داكنة بحلقات متداخلة تحدها العروق."),
        ["potato__late_blight"], ["aps_potato", "ucipm_potato"]),
    "potato__late_blight": E(
        "oomycete", "Phytophthora infestans",
        ("Water-soaked, pale-to-dark-green patches turning brown-black, often starting at leaf tips or edges; white mould on the underside at the lesion edge in humid weather; can kill foliage in days and rot tubers.",
         "بقع مائية خضراء فاتحة إلى داكنة تتحول إلى بنية سوداء، تبدأ غالبًا عند أطراف الأوراق أو حوافها؛ مع عفن أبيض على الوجه السفلي عند حافة البقعة في الجو الرطب؛ وقد تقتل المجموع الخضري خلال أيام وتعفّن الدرنات."),
        ("Spreading water-soaked patches with white growth underneath, no rings.", "بقع مائية متسعة مع نمو أبيض تحتها وبلا حلقات."),
        ["potato__early_blight"], ["aps_potato", "ucipm_potato"],
        note=("Hill up soil over tubers and kill haulms 2-3 weeks before harvest to protect tubers.",
              "اردم التربة فوق الدرنات (التحضين) وأزل المجموع الخضري قبل الحصاد بأسبوعين إلى ثلاثة لحماية الدرنات."),
        weather="hutton_late_blight"),
    # ------------------------------------------------------------------ pepper
    "bell_pepper__healthy": H(["ucipm_pepper"]),
    "bell_pepper__bacterial_spot": E(
        "bacterial", "Xanthomonas spp. (X. euvesicatoria and related species)",
        ("Small water-soaked spots that turn brown with a pale centre; leaves yellow and drop; raised, scabby spots on fruit.",
         "بقع صغيرة مائية تتحول إلى بنية بمركز فاتح؛ تصفر الأوراق وتتساقط؛ وتظهر على الثمار بقع بارزة متقشرة."),
        ("Small greasy brown spots and heavy leaf drop.", "بقع بنية دهنية صغيرة مع تساقط شديد للأوراق."),
        [], ["aps_pepper", "ucipm_pepper"]),
    # ------------------------------------------------------------------ cucumber
    "cucumber__healthy": H(["ucipm_cucurbits"]),
    "cucumber__powdery_mildew": E(
        "powdery_mildew", "Podosphaera xanthii (also Golovinomyces orontii)",
        ("White powdery patches on both leaf surfaces and stems that can be rubbed off; leaves later yellow and dry.",
         "بقع بيضاء مسحوقية على سطحي الورقة والسيقان يمكن إزالتها بالمسح؛ ثم تصفر الأوراق وتجف."),
        ("White powder ON the leaf that wipes off.", "مسحوق أبيض فوق الورقة يُزال بالمسح."),
        ["cucumber__angular_leaf_spot"], ["aps_cucurbit", "ucipm_cucurbits"]),
    "cucumber__angular_leaf_spot": E(
        "bacterial", "Pseudomonas syringae pv. lachrymans",
        ("Small water-soaked spots limited by veins (angular), turning tan and dry; the dead tissue falls out leaving ragged holes; milky droplets on the underside in humid mornings.",
         "بقع صغيرة مائية تحدها العروق (زاوية) تتحول إلى بنية فاتحة وتجف؛ ويسقط النسيج الميت تاركًا ثقوبًا ممزقة؛ وقطرات حليبية على الوجه السفلي في الصباح الرطب."),
        ("Angular spots that dry and fall out as holes; no fuzzy growth underneath.", "بقع زاوية تجف وتسقط مخلفة ثقوبًا؛ بلا نمو زغبي تحتها."),
        ["cucumber__powdery_mildew"], ["aps_cucurbit", "ucipm_cucurbits"],
        note=("Downy mildew (Pseudoperonospora cubensis) also makes angular yellow spots on cucumber but shows grey-purple fuzz on the underside; this model has no cucumber downy mildew class, so check the underside.",
              "البياض الزغبي (Pseudoperonospora cubensis) يسبب أيضًا بقعًا صفراء زاوية على الخيار لكن مع زغب رمادي بنفسجي على الوجه السفلي؛ وهذا النموذج لا يحتوي فئة للبياض الزغبي على الخيار، لذا افحص الوجه السفلي.")),
    "cucumber__bacterial_wilt": E(
        "bacterial_wilt_vector", "Erwinia tracheiphila",
        ("Individual leaves or whole runners wilt suddenly and do not recover overnight; cut stems ooze sticky strands when the cut ends are pulled apart slowly.",
         "تذبل أوراق منفردة أو أفرع كاملة فجأة ولا تستعيد نضارتها ليلًا؛ وعند قطع الساق وإبعاد طرفي القطع ببطء تظهر خيوط لزجة."),
        ("Sudden wilt with sticky strings from the cut stem.", "ذبول مفاجئ مع خيوط لزجة من الساق المقطوعة."),
        [], ["aps_cucurbit"],
        note=("Wilting can also come from root problems, nematodes or simple water stress; the sticky-string test helps confirm bacterial wilt.",
              "قد ينتج الذبول أيضًا عن مشكلات الجذور أو النيماتودا أو العطش؛ واختبار الخيوط اللزجة يساعد على تأكيد الذبول البكتيري.")),
    # ------------------------------------------------------------------ squash
    "squash__healthy": H(["ucipm_cucurbits"]),
    "squash__powdery_mildew": E(
        "powdery_mildew", "Podosphaera xanthii (also Golovinomyces orontii)",
        ("White powdery spots on leaves and stems that merge and can be rubbed off; older leaves first.",
         "بقع بيضاء مسحوقية على الأوراق والسيقان تندمج ويمكن مسحها؛ تبدأ على الأوراق الأقدم."),
        ("White powder that wipes off. (Note: some squash varieties have natural silver leaf markings, which do not wipe off.)",
         "مسحوق أبيض يُزال بالمسح. (ملاحظة: بعض أصناف الكوسة لها علامات فضية طبيعية على الأوراق لا تُزال بالمسح.)"),
        ["squash__yellow_mosaic_virus"], ["aps_cucurbit", "ucipm_cucurbits"]),
    "squash__yellow_mosaic_virus": E(
        "virus_aphid", "Zucchini yellow mosaic virus (ZYMV, potyvirus)",
        ("Bright yellow mosaic, leaf blistering and narrowing, stunting; fruit knobby, distorted and discoloured.",
         "تبرقش أصفر لامع، وتبثّر الأوراق وضيقها، وتقزم؛ وثمار متعقدة مشوهة متغيرة اللون."),
        ("Yellow mosaic with distorted leaves and knobby fruit.", "تبرقش أصفر مع أوراق مشوهة وثمار متعقدة."),
        ["squash__powdery_mildew"], ["aps_cucurbit", "ucipm_cucurbits"]),
    # ------------------------------------------------------------------ eggplant
    "eggplant__healthy": H(["fao_gap_greenhouse"]),
    "eggplant__cercospora_leaf_spot": E(
        "fungal_leaf_spot", "Cercospora melongenae",
        ("Round to irregular yellowish spots that turn brown, sometimes with faint rings and grey fungal growth in the centre; heavy infections cause leaf drop.",
         "بقع دائرية إلى غير منتظمة مصفرة تتحول إلى بنية، أحيانًا بحلقات خفيفة ونمو فطري رمادي في المركز؛ والإصابة الشديدة تسبب تساقط الأوراق."),
        ("Chlorotic-bordered brown spots with grey centre growth.", "بقع بنية بحواف مصفرة ونمو رمادي في المركز."),
        [], ["frac"],
        note=("Fewer extension references cover eggplant leaf spots; confirm with an extension office before spraying.",
              "المراجع الإرشادية عن تبقعات أوراق الباذنجان أقل؛ تأكد من مكتب الإرشاد قبل الرش.")),
    # ------------------------------------------------------------------ lettuce
    "lettuce__healthy": H(["ucipm_lettuce"]),
    "lettuce__downy_mildew": E(
        "oomycete", "Bremia lactucae",
        ("Pale-green to yellow angular patches bounded by veins on older leaves, with white downy growth on the underside; patches turn brown.",
         "بقع زاوية خضراء باهتة إلى صفراء تحدها العروق على الأوراق الأقدم، مع نمو أبيض زغبي على الوجه السفلي؛ ثم تتحول البقع إلى البني."),
        ("Vein-bounded yellow patches with white fuzz underneath.", "بقع صفراء تحدها العروق مع زغب أبيض تحتها."),
        ["lettuce__mosaic_virus"], ["aps_lettuce", "ucipm_lettuce"]),
    "lettuce__mosaic_virus": E(
        "virus_aphid", "Lettuce mosaic virus (LMV, potyvirus), seed-borne",
        ("Mottling and vein clearing, leaf distortion, stunting; heads fail to form properly.",
         "تبرقش وشفافية العروق، وتشوه الأوراق، وتقزم؛ ولا تتكوّن الرؤوس بشكل سليم."),
        ("Mosaic and distortion without fuzzy growth.", "تبرقش وتشوه بلا نمو زغبي."),
        ["lettuce__downy_mildew"], ["aps_lettuce", "ucipm_lettuce"],
        note=("LMV is seed-borne: use seed certified as LMV-tested.", "فيروس موزاييك الخس ينتقل بالبذور: استخدم بذورًا معتمدة مفحوصة منه.")),
    # ------------------------------------------------------------------ brassicas
    "cabbage__healthy": H(["ucipm_cole"]),
    "cabbage__alternaria_leaf_spot": E(
        "fungal_leaf_spot", "Alternaria brassicicola / A. brassicae",
        ("Round brown-to-black spots with concentric rings, sometimes with a yellow halo; centres may fall out.",
         "بقع دائرية بنية إلى سوداء بحلقات متداخلة، أحيانًا بهالة صفراء؛ وقد يسقط مركزها."),
        ("Target-like dark ringed spots.", "بقع داكنة حلقية تشبه الهدف."), [], ["aps_brassica", "ucipm_cole"],
        note=("Alternaria of brassicas is seed-borne: use treated or tested seed.", "ألترناريا الصليبيات تنتقل بالبذور: استخدم بذورًا معاملة أو مفحوصة.")),
    "cauliflower__healthy": H(["ucipm_cole"]),
    "cauliflower__alternaria_leaf_spot": E(
        "fungal_leaf_spot", "Alternaria brassicicola / A. brassicae",
        ("Round dark spots with concentric rings on leaves; brown to black spots on curds reduce quality.",
         "بقع داكنة دائرية بحلقات متداخلة على الأوراق؛ وبقع بنية إلى سوداء على الأقراص تقلل الجودة."),
        ("Target-like dark ringed spots.", "بقع داكنة حلقية تشبه الهدف."), [], ["aps_brassica", "ucipm_cole"]),
    "broccoli__healthy": H(["ucipm_cole"]),
    "broccoli__downy_mildew": E(
        "oomycete", "Hyaloperonospora parasitica (H. brassicae)",
        ("Yellow, angular patches on the upper leaf surface with white-grey downy growth underneath; dark streaks inside the heads in some cases.",
         "بقع صفراء زاوية على الوجه العلوي للورقة مع نمو زغبي أبيض رمادي تحتها؛ وأحيانًا خطوط داكنة داخل الرؤوس."),
        ("Yellow patches with grey-white fuzz underneath.", "بقع صفراء مع زغب أبيض رمادي تحتها."), [], ["aps_brassica", "ucipm_cole"]),
    # ------------------------------------------------------------------ bean
    "bean__healthy": H(["ucipm_beans"]),
    "bean__halo_blight": E(
        "bacterial", "Pseudomonas savastanoi pv. phaseolicola",
        ("Small water-soaked spots surrounded by a wide light-green to yellow halo; pods show greasy spots.",
         "بقع صغيرة مائية تحيط بها هالة واسعة خضراء فاتحة إلى صفراء؛ وتظهر على القرون بقع دهنية."),
        ("Tiny spot with a wide yellow-green halo.", "بقعة صغيرة بهالة صفراء مخضرة واسعة."),
        ["bean__rust", "bean__mosaic_virus"], ["aps_bean", "ucipm_beans"],
        note=("Halo blight is seed-borne; never save seed from infected plants.", "اللفحة الهالية تنتقل بالبذور؛ لا تحتفظ أبدًا ببذور من نباتات مصابة.")),
    "bean__rust": E(
        "rust", "Uromyces appendiculatus",
        ("Small reddish-brown powdery pustules, mostly on the leaf underside, often with a yellow halo.",
         "بثرات صغيرة بنية محمرة مسحوقية، غالبًا على الوجه السفلي للورقة، كثيرًا مع هالة صفراء."),
        ("Raised rusty pustules that leave powder on a finger.", "بثرات بارزة بلون الصدأ تترك مسحوقًا على الإصبع."),
        ["bean__halo_blight"], ["aps_bean", "ucipm_beans"]),
    "bean__mosaic_virus": E(
        "virus_aphid", "Bean common mosaic virus (BCMV) and related potyviruses, seed-borne",
        ("Light/dark green mosaic, leaves puckered, narrow or cupped downward; plants stunted.",
         "تبرقش أخضر فاتح وداكن، وأوراق متجعدة ضيقة أو ملتفة للأسفل؛ ونباتات متقزمة."),
        ("Mosaic with puckered, down-curled leaves.", "تبرقش مع أوراق متجعدة ملتفة للأسفل."),
        ["bean__halo_blight"], ["aps_bean", "ucipm_beans"]),
    # ------------------------------------------------------------------ corn
    "corn__healthy": H(["ucipm_corn"]),
    "corn__common_rust": E(
        "rust", "Puccinia sorghi",
        ("Elongated, powdery, cinnamon-brown pustules on BOTH leaf surfaces.", "بثرات مستطيلة مسحوقية بنية بلون القرفة على سطحي الورقة."),
        ("Powdery brown pustules on both leaf sides.", "بثرات بنية مسحوقية على وجهي الورقة."),
        ["corn__gray_leaf_spot", "corn__northern_leaf_spot"], ["aps_corn", "ucipm_corn"]),
    "corn__northern_leaf_blight": E(
        "fungal_leaf_spot", "Exserohilum turcicum",
        ("Long (about 2.5-15 cm) cigar-shaped grey-green to tan lesions, lower leaves first.",
         "بقع طويلة (حوالي 2.5-15 سم) على شكل السيجار رمادية مخضرة إلى بنية فاتحة، تبدأ على الأوراق السفلية."),
        ("Long cigar-shaped lesions not limited by veins.", "بقع طويلة على شكل السيجار لا تحدها العروق."),
        ["corn__gray_leaf_spot", "corn__northern_leaf_spot"], ["aps_corn"]),
    "corn__gray_leaf_spot": E(
        "fungal_leaf_spot", "Cercospora zeae-maydis",
        ("Narrow, rectangular, tan-to-grey lesions running parallel to and limited by the leaf veins.",
         "بقع ضيقة مستطيلة بنية فاتحة إلى رمادية موازية لعروق الورقة ومحدودة بها."),
        ("Rectangular, vein-limited, matchstick-like lesions.", "بقع مستطيلة محدودة بالعروق تشبه عود الثقاب."),
        ["corn__northern_leaf_blight", "corn__common_rust"], ["aps_corn"]),
    "corn__northern_leaf_spot": E(
        "fungal_leaf_spot", "Bipolaris zeicola",
        ("Small oval to oblong tan-brown spots, sometimes with darker borders or faint rings.",
         "بقع صغيرة بيضاوية إلى مستطيلة بنية فاتحة، أحيانًا بحواف أدكن أو حلقات خفيفة."),
        ("Short oval spots, much shorter than northern leaf blight.", "بقع بيضاوية قصيرة أقصر كثيرًا من اللفحة الشمالية."),
        ["corn__northern_leaf_blight", "corn__gray_leaf_spot"], ["aps_corn"]),
    "corn__corn_smut": E(
        "smut", "Mycosarcoma maydis (Ustilago maydis)",
        ("Swollen white-grey galls on ears, tassels, stems or leaves that turn into masses of black powdery spores.",
         "أورام منتفخة بيضاء رمادية على الكيزان أو النورات المذكرة أو السيقان أو الأوراق تتحول إلى كتل من الجراثيم السوداء المسحوقية."),
        ("Large galls filled with black spores.", "أورام كبيرة مملوءة بجراثيم سوداء."), [], ["aps_corn"]),
    # ------------------------------------------------------------------ garlic
    "garlic__healthy": H(["ucipm_onion"]),
    "garlic__rust": E(
        "rust", "Puccinia allii",
        ("Small orange to reddish pustules on leaves, which later yellow and die back.", "بثرات صغيرة برتقالية إلى محمرة على الأوراق، ثم تصفر الأوراق وتجف من أطرافها."),
        ("Orange powdery pustules.", "بثرات برتقالية مسحوقية."), ["garlic__leaf_blight"], ["aps_onion", "ucipm_onion"]),
    "garlic__leaf_blight": E(
        "fungal_leaf_spot", "Stemphylium vesicarium / Alternaria porri (leaf blight and purple blotch complex)",
        ("Small water-soaked spots that grow into elongated tan to purplish lesions, often with concentric zones; leaf tips die back.",
         "بقع صغيرة مائية تتحول إلى بقع مستطيلة بنية فاتحة إلى أرجوانية، غالبًا بمناطق متداخلة؛ وتجف أطراف الأوراق."),
        ("Elongated tan-purple lesions, no powdery pustules.", "بقع مستطيلة بنية أرجوانية بلا بثرات مسحوقية."),
        ["garlic__rust"], ["aps_onion", "ucipm_onion"]),
    # ------------------------------------------------------------------ grape
    "grape__healthy": H(["ucipm_grape"]),
    "grape__downy_mildew": E(
        "oomycete", "Plasmopara viticola",
        ("Yellowish 'oil spots' on the upper leaf surface with white downy growth underneath; infected berries turn grey or brown and shrivel.",
         "بقع صفراء 'زيتية' على الوجه العلوي للورقة مع نمو أبيض زغبي تحتها؛ وتتحول الحبات المصابة إلى رمادية أو بنية وتنكمش."),
        ("Oily yellow spots with white fuzz on the underside.", "بقع صفراء زيتية مع زغب أبيض على الوجه السفلي."),
        ["grape__leaf_spot", "grape__black_rot"], ["aps_grape", "ucipm_grape"], weather="three_tens_downy_mildew"),
    "grape__black_rot": E(
        "fungal_leaf_spot", "Guignardia bidwellii (Phyllosticta ampelicida)",
        ("Round tan spots with a dark-brown border and a ring of tiny black dots (fruiting bodies); berries turn black and shrivel into hard 'mummies'.",
         "بقع دائرية بنية فاتحة بحافة بنية داكنة وحلقة من نقاط سوداء دقيقة (أجسام ثمرية)؛ وتسودّ الحبات وتنكمش إلى 'مومياوات' صلبة."),
        ("Tan spots ringed with black pin-point dots.", "بقع بنية فاتحة محاطة بنقاط سوداء دقيقة."),
        ["grape__isariopsis_leaf_spot", "grape__leaf_spot"], ["aps_grape"],
        note=("Remove mummified berries and infected canes during pruning; they carry the disease to the next season.",
              "أزل الحبات المحنطة والقصبات المصابة أثناء التقليم؛ فهي تنقل المرض إلى الموسم التالي.")),
    "grape__isariopsis_leaf_spot": E(
        "fungal_leaf_spot", "Pseudocercospora vitis (Isariopsis leaf spot)",
        ("Irregular dark-brown to black spots, often with a yellow margin, mostly on older leaves late in the season.",
         "بقع غير منتظمة بنية داكنة إلى سوداء، غالبًا بحافة صفراء، على الأوراق الأقدم في آخر الموسم."),
        ("Irregular dark spots without the black-dot ring of black rot.", "بقع داكنة غير منتظمة بلا حلقة النقاط السوداء الخاصة بالعفن الأسود."),
        ["grape__black_rot", "grape__leaf_spot"], ["aps_grape"]),
    "grape__leaf_spot": E(
        "fungal_leaf_spot", "various leaf-spotting fungi (PlantWild 'grape leaf spot' class)",
        ("Brown leaf spots of various sizes not matching a more specific grape disease.", "بقع بنية على الأوراق بأحجام مختلفة لا تطابق مرضًا أكثر تحديدًا في العنب."),
        ("Non-specific brown spots.", "بقع بنية غير محددة."),
        ["grape__black_rot", "grape__isariopsis_leaf_spot", "grape__downy_mildew"], ["aps_grape"],
        note=("This is a broad class: have the specific cause confirmed before choosing a fungicide.", "هذه فئة عامة: أكّد السبب المحدد قبل اختيار المبيد.")),
    "grape__esca": E(
        "trunk_disease", "Esca complex (Phaeomoniella chlamydospora, Phaeoacremonium spp., Fomitiporia spp.)",
        ("'Tiger-stripe' leaves: yellow or red-brown bands between the veins with green tissue along the veins; berries may show dark spots; sudden collapse of a vine in hot weather.",
         "أوراق 'مخططة كالنمر': أشرطة صفراء أو بنية محمرة بين العروق مع بقاء النسيج على امتداد العروق أخضر؛ وقد تظهر على الحبات بقع داكنة؛ وانهيار مفاجئ للكرمة في الحر."),
        ("Tiger-stripe interveinal discoloration.", "تلوّن بين العروق على شكل خطوط النمر."), ["grape__leafroll_virus"], ["aps_grape", "ucipm_grape"]),
    "grape__leafroll_virus": E(
        "virus_planting_material", "Grapevine leafroll-associated viruses (GLRaV), spread by mealybugs and planting material",
        ("In autumn, leaves roll downward; red varieties turn red-purple between the veins while the main veins stay green; white varieties turn yellowish.",
         "في الخريف تلتف الأوراق إلى الأسفل؛ وتتحول الأصناف الحمراء إلى الأحمر الأرجواني بين العروق مع بقاء العروق الرئيسية خضراء؛ وتصفر الأصناف البيضاء."),
        ("Downward-rolled leaves with green main veins.", "أوراق ملتفة للأسفل مع عروق رئيسية خضراء."),
        ["grape__esca"], ["aps_grape", "ucipm_grape"],
        note=("Control mealybugs, which spread leafroll between vines.", "كافح البق الدقيقي الذي ينقل مرض التفاف الأوراق بين الكروم.")),
    # ------------------------------------------------------------------ strawberry
    "strawberry__healthy": H(["ucipm_strawberry"]),
    "strawberry__leaf_scorch": E(
        "fungal_leaf_spot", "Diplocarpon earlianum",
        ("Many small, irregular dark-purple blotches WITHOUT a pale centre; they merge and the leaf looks scorched.",
         "بقع صغيرة كثيرة غير منتظمة أرجوانية داكنة بلا مركز فاتح؛ تندمج فتبدو الورقة محترقة."),
        ("Purple blotches with no pale centre.", "بقع أرجوانية بلا مركز فاتح."),
        ["strawberry__leaf_spot", "strawberry__angular_leaf_spot"], ["aps_strawberry", "ucipm_strawberry"]),
    "strawberry__leaf_spot": E(
        "fungal_leaf_spot", "Mycosphaerella fragariae (Ramularia tulasnei)",
        ("Small round spots with a white to tan centre and a dark-purple border.", "بقع صغيرة دائرية بمركز أبيض إلى بني فاتح وحافة أرجوانية داكنة."),
        ("Pale centre ringed with purple.", "مركز فاتح محاط بالأرجواني."),
        ["strawberry__leaf_scorch", "strawberry__angular_leaf_spot"], ["aps_strawberry", "ucipm_strawberry"]),
    "strawberry__angular_leaf_spot": E(
        "bacterial", "Xanthomonas fragariae",
        ("Small water-soaked angular spots on the underside that look translucent against light, later reddish-brown; sticky ooze in humid conditions.",
         "بقع صغيرة مائية زاوية على الوجه السفلي تبدو شفافة عند تعريضها للضوء، ثم تصبح بنية محمرة؛ مع إفراز لزج في الرطوبة."),
        ("Translucent angular spots when held up to light.", "بقع زاوية شفافة عند رفع الورقة نحو الضوء."),
        ["strawberry__leaf_scorch", "strawberry__leaf_spot"], ["aps_strawberry", "ucipm_strawberry"],
        note=("Fungicides do not work on this bacterium; use clean nursery plants and drip irrigation.",
              "المبيدات الفطرية لا تؤثر في هذه البكتيريا؛ استخدم شتلات نظيفة والري بالتنقيط.")),
    "strawberry__powdery_mildew": E(
        "powdery_mildew", "Podosphaera aphanis",
        ("Leaf edges curl UPWARD; white powdery growth on the underside; purple-red blotches on the leaf.",
         "تلتف حواف الأوراق إلى الأعلى؛ ونمو أبيض مسحوقي على الوجه السفلي؛ وبقع أرجوانية حمراء على الورقة."),
        ("Upward-curled leaves with white powder underneath.", "أوراق ملتفة للأعلى مع مسحوق أبيض تحتها."),
        ["strawberry__leaf_scorch"], ["aps_strawberry", "ucipm_strawberry"]),
    "strawberry__anthracnose": E(
        "fungal_leaf_spot", "Colletotrichum acutatum species complex / C. gloeosporioides",
        ("Dark, sunken lesions on runners, petioles and fruit (fruit rot with orange spore masses); crown infection makes the plant wilt.",
         "بقع داكنة غائرة على المدادات وأعناق الأوراق والثمار (عفن الثمار مع كتل جراثيم برتقالية)؛ وإصابة التاج تسبب ذبول النبات."),
        ("Sunken dark lesions with orange spore masses.", "بقع داكنة غائرة مع كتل جراثيم برتقالية."),
        [], ["aps_strawberry", "ucipm_strawberry"],
        note=("Usually introduced on infected nursery plants: buy certified transplants.", "يدخل غالبًا مع شتلات المشتل المصابة: اشترِ شتلات معتمدة.")),
    # ------------------------------------------------------------------ apple
    "apple__healthy": H(["ucipm_apple"]),
    "apple__scab": E(
        "fungal_leaf_spot", "Venturia inaequalis",
        ("Olive-green to black velvety spots on leaves and fruit; fruit spots become corky and cracked.",
         "بقع مخملية زيتونية خضراء إلى سوداء على الأوراق والثمار؛ وتصبح بقع الثمار فلينية متشققة."),
        ("Velvety olive spots.", "بقع مخملية زيتونية."), ["apple__frog_eye_leaf_spot"], ["aps_apple", "ucipm_apple"]),
    "apple__black_rot": E(
        "fungal_leaf_spot", "Diplodia seriata (Botryosphaeria obtusa)",
        ("Leaves: purple-bordered spots with tan centres ('frog-eye'); fruit: brown rot with rings, turning black; cankers on limbs.",
         "الأوراق: بقع بمراكز بنية فاتحة وحواف أرجوانية ('عين الضفدع')؛ الثمار: عفن بني حلقي يتحول إلى أسود؛ وتقرحات على الأفرع."),
        ("Frog-eye leaf spots plus fruit rot or limb cankers.", "بقع عين الضفدع مع عفن الثمار أو تقرحات الأفرع."),
        ["apple__frog_eye_leaf_spot", "apple__scab"], ["aps_apple"],
        note=("Prune out dead wood and cankers and remove mummified fruit.", "قلّم الخشب الميت والتقرحات وأزل الثمار المحنطة.")),
    "apple__frog_eye_leaf_spot": E(
        "fungal_leaf_spot", "Diplodia seriata (leaf phase of black rot)",
        ("Small purple spots that enlarge into tan centres with purple margins.", "بقع أرجوانية صغيرة تتسع إلى مراكز بنية فاتحة بحواف أرجوانية."),
        ("Tan centre, purple ring.", "مركز بني فاتح وحلقة أرجوانية."), ["apple__black_rot", "apple__scab"], ["aps_apple"]),
    "apple__cedar_apple_rust": E(
        "rust", "Gymnosporangium juniperi-virginianae (and related Gymnosporangium spp.)",
        ("Bright yellow-orange spots on the upper leaf surface; later small tubes on the underside.", "بقع صفراء برتقالية لامعة على الوجه العلوي؛ ثم أنابيب صغيرة على الوجه السفلي."),
        ("Bright orange spots.", "بقع برتقالية لامعة."), ["apple__scab"], ["aps_apple", "ucipm_apple"],
        note=("The fungus needs juniper/cedar as an alternate host; removing nearby junipers breaks the cycle.",
              "يحتاج الفطر إلى العرعر كعائل بديل؛ وإزالة أشجار العرعر القريبة تكسر دورة المرض.")),
    "apple__powdery_mildew": E(
        "powdery_mildew", "Podosphaera leucotricha",
        ("White felt-like growth on young leaves and shoots; leaves narrow and fold.", "نمو أبيض لبادي على الأوراق والأفرع الحديثة؛ وتضيق الأوراق وتنطوي."),
        ("White felt on new growth.", "لباد أبيض على النموات الحديثة."), [], ["aps_apple", "ucipm_apple"],
        note=("Prune out white, infected shoot tips in winter.", "قلّم أطراف الأفرع البيضاء المصابة في الشتاء.")),
    "apple__mosaic_virus": E(
        "virus_planting_material", "Apple mosaic virus (ApMV), graft-transmitted",
        ("Bright cream-yellow spots, bands along veins or line patterns on spring leaves.", "بقع صفراء كريمية لامعة أو أشرطة على امتداد العروق أو أنماط خطية على أوراق الربيع."),
        ("Cream-yellow patterns without lesions.", "أنماط صفراء كريمية بلا بقع ميتة."), [], ["aps_apple"]),
}
