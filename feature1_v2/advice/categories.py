"""
Management templates by disease category (English / Arabic).

Why categories: most diseases of one biological type are managed the same
way (a foliar fungal leaf spot on tomato and one on cabbage need the same
sanitation, water and fungicide-group logic). Writing the shared part once
and adding disease-specific notes in entries.py keeps the advice consistent
and limits the room for errors in 66 near-duplicate texts.

Chemical control is given ONLY as mode-of-action groups (FRAC for fungicides,
IRAC for insecticides / acaricides), never as product names or doses: the
products registered in Saudi Arabia, their doses and pre-harvest intervals
are on the label of a MEWA-registered product. Every chemical section ends
with that instruction.

Important distinction kept here: late blight and downy mildews are
OOMYCETES, not true fungi. Several common fungicide groups do not control
them, so they get their own template.
"""

LABEL_RULE = {
    "en": "Use only a product registered by the Ministry of Environment, Water and Agriculture (MEWA) for this crop "
          "and disease, and follow its label for dose, interval, protective equipment and pre-harvest interval. "
          "Rotate between mode-of-action groups; do not repeat one group back to back.",
    "ar": "استخدم فقط مبيدًا مسجّلًا لدى وزارة البيئة والمياه والزراعة لهذا المحصول وهذا المرض، والتزم بما في ملصقه من "
          "جرعة وفترة بين الرشات ومعدات وقاية وفترة أمان قبل الحصاد. بدّل بين مجموعات طريقة التأثير ولا تكرر المجموعة نفسها في رشّتين متتاليتين.",
}

EXTENSION = {
    "en": "Contact your nearest MEWA agricultural extension office (or a licensed plant clinic) if the problem spreads "
          "to many plants within a few days, if fruit is affected, or if you are unsure of the diagnosis. Take a "
          "fresh sample of affected leaves in a paper bag.",
    "ar": "تواصل مع أقرب مكتب إرشاد زراعي تابع لوزارة البيئة والمياه والزراعة (أو عيادة نباتية مرخّصة) إذا انتشرت المشكلة إلى نباتات كثيرة خلال أيام، "
          "أو أصابت الثمار، أو لم تكن متأكدًا من التشخيص. خذ معك عينة حديثة من الأوراق المصابة في كيس ورقي.",
}

CATEGORIES = {
    "healthy": {
        "name": {"en": "No disease detected", "ar": "لم يُكتشف مرض"},
        "immediate": {"en": ["No treatment is needed.",
                             "Check the underside of leaves and new growth once a week; early detection matters most."],
                      "ar": ["لا حاجة لأي علاج.",
                             "افحص الوجه السفلي للأوراق والنموات الحديثة مرة أسبوعيًا؛ الاكتشاف المبكر هو الأهم."]},
        "cultural": {"en": ["Water at the soil (drip) rather than over the leaves.",
                            "Keep spacing and pruning that let air move through the canopy."],
                     "ar": ["اسقِ عند التربة (بالتنقيط) وليس فوق الأوراق.",
                            "حافظ على مسافات زراعة وتقليم تسمح بمرور الهواء بين النباتات."]},
        "chemical_groups": None,
        "prevention": {"en": ["Start from certified seed or healthy transplants.", "Remove weeds that host pests and viruses."],
                       "ar": ["ابدأ ببذور معتمدة أو شتلات سليمة.", "أزل الحشائش التي تأوي الآفات والفيروسات."]},
        "sources": ["fao_gap_greenhouse"],
    },
    "fungal_leaf_spot": {
        "name": {"en": "Fungal leaf disease", "ar": "مرض فطري على الأوراق"},
        "immediate": {"en": ["Remove the most affected leaves and fallen leaves; bag them and take them off the field (do not compost).",
                             "Stop overhead watering; water early in the day at the soil.",
                             "Do not work among the plants while the leaves are wet."],
                      "ar": ["أزل أكثر الأوراق إصابة والأوراق المتساقطة، وضعها في أكياس وأخرجها من الحقل (لا تضعها في السماد).",
                             "أوقف الري بالرش فوق الأوراق؛ واسقِ في الصباح الباكر عند التربة.",
                             "لا تعمل بين النباتات وأوراقها مبتلة."]},
        "cultural": {"en": ["Improve air flow: wider spacing, staking, removing lower leaves touching the soil.",
                            "Mulch the soil so rain or irrigation splash does not carry spores onto leaves.",
                            "Rotate away from the same crop family for 2-3 seasons where the fungus survives on debris."],
                     "ar": ["حسّن التهوية: مسافات أوسع، تدعيم النباتات، وإزالة الأوراق السفلية الملامسة للتربة.",
                            "غطِّ التربة (تغطية عضوية أو بلاستيكية) حتى لا ينقل رذاذ الماء الجراثيم إلى الأوراق.",
                            "اتبع دورة زراعية بعيدًا عن العائلة النباتية نفسها لمدة 2-3 مواسم عندما يعيش الفطر على بقايا النبات."]},
        "chemical_groups": {"en": "Protectant fungicides (FRAC M03 dithiocarbamates, M05 chloronitriles, M01 copper) applied "
                                  "before or at the first symptoms; systemic groups (FRAC 3 DMI, 7 SDHI, 11 QoI) only in "
                                  "rotation or mixed with a protectant, because resistance to them develops quickly.",
                            "ar": "مبيدات فطرية واقية (مجموعات FRAC: M03 ثنائي ثيوكاربامات، M05 كلورونيتريل، M01 النحاس) تُرش قبل "
                                  "ظهور الأعراض أو عند أولها؛ والمجموعات الجهازية (FRAC 3، 7، 11) فقط بالتناوب أو مخلوطة مع مبيد واقٍ "
                                  "لأن المقاومة لها تتطور بسرعة."},
        "prevention": {"en": ["Use resistant or tolerant varieties where available.", "Remove and destroy crop debris after harvest."],
                       "ar": ["استخدم أصنافًا مقاومة أو متحملة إن وُجدت.", "أزل بقايا المحصول وأتلفها بعد الحصاد."]},
        "sources": ["frac", "fao_gap_greenhouse"],
    },
    "oomycete": {
        "name": {"en": "Water-mould disease (oomycete) - spreads fast in humid weather",
                 "ar": "مرض من الفطريات البيضية (أوميسيت) - ينتشر بسرعة في الجو الرطب"},
        "immediate": {"en": ["Act today: this group can destroy a crop within a week in cool, humid or dewy weather.",
                             "Remove and bag infected leaves (and whole plants if most leaves are affected); do not leave them in the field.",
                             "Stop overhead irrigation and improve ventilation (open greenhouse vents, reduce night humidity)."],
                      "ar": ["تصرّف اليوم: هذه المجموعة قد تدمّر المحصول خلال أسبوع في الجو البارد الرطب أو مع الندى.",
                             "أزل الأوراق المصابة وضعها في أكياس (والنبات كاملًا إذا أصيبت معظم أوراقه)؛ ولا تتركها في الحقل.",
                             "أوقف الري بالرش وحسّن التهوية (افتح فتحات البيت المحمي وقلّل الرطوبة الليلية)."]},
        "cultural": {"en": ["Avoid long leaf wetness: irrigate in the morning, at the soil.",
                            "Do not crowd plants; in greenhouses avoid condensation dripping on leaves.",
                            "Destroy volunteer plants and cull piles (for potato) that carry the pathogen between seasons."],
                     "ar": ["تجنّب بقاء الأوراق مبتلة لفترات طويلة: اسقِ صباحًا وعند التربة.",
                            "لا تزرع النباتات متقاربة جدًا؛ وفي البيوت المحمية امنع تساقط قطرات التكثف على الأوراق.",
                            "أتلف النباتات النابتة ذاتيًا وأكوام الدرنات المستبعدة (في البطاطس) التي تنقل المرض بين المواسم."]},
        "chemical_groups": {"en": "Use fungicides that act on oomycetes: protectants (FRAC M03, M05, M01) before infection, and "
                                  "oomycete-specific groups such as FRAC 40 (CAA), 21 (QiI), 43, 27 or 4 (phenylamides; "
                                  "resistance is widespread, use only in mixtures). Many general fungicide groups "
                                  "(e.g. most FRAC 3 DMIs) do not control oomycetes.",
                            "ar": "استخدم مبيدات تؤثر على الفطريات البيضية: الواقية (FRAC M03، M05، M01) قبل الإصابة، والمجموعات "
                                  "المتخصصة مثل FRAC 40 و21 و43 و27 أو 4 (الفينيل أميدات؛ المقاومة لها منتشرة فلا تُستخدم إلا مخلوطة). "
                                  "كثير من المبيدات الفطرية العامة (مثل معظم مجموعة FRAC 3) لا تكافح هذه الأمراض."},
        "prevention": {"en": ["Plant certified disease-free seed tubers / transplants.", "Follow the weather-risk alert below and protect before risky periods."],
                       "ar": ["ازرع تقاوي أو شتلات معتمدة خالية من المرض.", "تابع تنبيه خطر الطقس أدناه ووفّر الحماية قبل الفترات الخطرة."]},
        "sources": ["frac", "fao_gap_greenhouse"],
    },
    "powdery_mildew": {
        "name": {"en": "Powdery mildew (fungal)", "ar": "البياض الدقيقي (فطري)"},
        "immediate": {"en": ["Remove the worst affected older leaves.",
                             "Powdery mildew does NOT need wet leaves; it thrives in shade, dense canopies and dry air with mild nights, so it is common in Saudi greenhouses and in winter fields."],
                      "ar": ["أزل الأوراق القديمة الأشد إصابة.",
                             "البياض الدقيقي لا يحتاج إلى أوراق مبتلة؛ ينتشر في الظل والنباتات الكثيفة والهواء الجاف مع ليالٍ معتدلة، لذا هو شائع في البيوت المحمية وفي الحقول شتاءً في المملكة."]},
        "cultural": {"en": ["Thin the canopy and improve light and air movement.", "Avoid excess nitrogen, which produces soft, susceptible growth."],
                     "ar": ["خفّف كثافة النباتات وحسّن الإضاءة وحركة الهواء.", "تجنّب الإفراط في التسميد النيتروجيني الذي ينتج نموًا طريًا قابلًا للإصابة."]},
        "chemical_groups": {"en": "Sulfur (FRAC M02; do not apply in high heat, roughly above 32-35 degC, or close to an oil spray), "
                                  "potassium bicarbonate or oils (contact), and systemic groups FRAC 3 (DMI), 7 (SDHI), 11 (QoI), "
                                  "13 or 50 in rotation. Start at the first spots: established infections are hard to stop.",
                            "ar": "الكبريت (FRAC M02؛ لا يُرش في الحر الشديد، فوق 32-35 درجة تقريبًا، ولا قرب رشة زيت)، وبيكربونات "
                                  "البوتاسيوم أو الزيوت (بالملامسة)، والمجموعات الجهازية FRAC 3 و7 و11 و13 أو 50 بالتناوب. ابدأ عند أول البقع "
                                  "لأن الإصابة المستقرة يصعب إيقافها."},
        "prevention": {"en": ["Choose powdery-mildew-resistant varieties (common for cucumber, squash and melon)."],
                       "ar": ["اختر أصنافًا مقاومة للبياض الدقيقي (متوفرة عادة للخيار والكوسة والشمام)."]},
        "sources": ["frac"],
    },
    "rust": {
        "name": {"en": "Rust (fungal)", "ar": "الصدأ (فطري)"},
        "immediate": {"en": ["Remove heavily infected leaves where practical.",
                             "Rust spores spread by wind; check neighbouring plants."],
                      "ar": ["أزل الأوراق شديدة الإصابة متى أمكن.",
                             "جراثيم الصدأ تنتقل بالرياح؛ افحص النباتات المجاورة."]},
        "cultural": {"en": ["Avoid long leaf wetness (morning irrigation, at the soil).", "Remove volunteer plants and alternate hosts where relevant."],
                     "ar": ["تجنّب بقاء الأوراق مبتلة طويلًا (ري صباحي عند التربة).", "أزل النباتات النابتة ذاتيًا والعوائل البديلة عند وجودها."]},
        "chemical_groups": {"en": "FRAC 3 (DMI) and 11 (QoI) systemic fungicides, or protectants (FRAC M03, M05), applied at the first pustules.",
                            "ar": "مبيدات جهازية من مجموعتي FRAC 3 و11، أو مبيدات واقية (FRAC M03، M05)، عند ظهور أول البثرات."},
        "prevention": {"en": ["Use resistant varieties."], "ar": ["استخدم أصنافًا مقاومة."]},
        "sources": ["frac"],
    },
    "bacterial": {
        "name": {"en": "Bacterial disease", "ar": "مرض بكتيري"},
        "immediate": {"en": ["Remove affected leaves on a dry day and disinfect tools afterwards.",
                             "Do not touch or prune plants while they are wet: water and hands spread bacteria.",
                             "Fungicides do not cure bacterial diseases."],
                      "ar": ["أزل الأوراق المصابة في يوم جاف وعقّم الأدوات بعدها.",
                             "لا تلمس النباتات ولا تقلّمها وهي مبتلة: الماء والأيدي ينقلان البكتيريا.",
                             "المبيدات الفطرية لا تعالج الأمراض البكتيرية."]},
        "cultural": {"en": ["Switch to drip irrigation; overhead water splash is the main spread route.",
                            "Rotate away from the crop (and its family) for at least 2 seasons; remove debris."],
                     "ar": ["انتقل إلى الري بالتنقيط؛ رذاذ الري العلوي هو طريق الانتشار الرئيسي.",
                            "اتبع دورة زراعية بعيدًا عن المحصول وعائلته لموسمين على الأقل؛ وأزل بقايا النبات."]},
        "chemical_groups": {"en": "Copper compounds (FRAC M01) can slow spread as a protectant, but control is partial and "
                                  "copper-resistant strains are common. Prevention matters more than spraying.",
                            "ar": "مركبات النحاس (FRAC M01) قد تبطئ الانتشار كوقاية، لكن المكافحة جزئية والسلالات المقاومة للنحاس شائعة. "
                                  "الوقاية أهم من الرش."},
        "prevention": {"en": ["Use certified (pathogen-tested) seed and healthy transplants; these bacteria are often seed-borne."],
                       "ar": ["استخدم بذورًا معتمدة (مفحوصة) وشتلات سليمة؛ فهذه البكتيريا تنتقل غالبًا عبر البذور."]},
        "sources": ["frac", "fao_gap_greenhouse"],
    },
    "virus_whitefly": {
        "name": {"en": "Virus spread by whiteflies - no cure", "ar": "فيروس ينقله الذباب الأبيض - لا علاج له"},
        "immediate": {"en": ["There is no cure for an infected plant. Pull out and bag infected plants early, especially young ones, to remove the virus source.",
                             "Check leaf undersides for whiteflies; yellow sticky traps show how many there are."],
                      "ar": ["لا يوجد علاج للنبات المصاب. اقلع النباتات المصابة مبكرًا وضعها في أكياس، خاصة الصغيرة، لإزالة مصدر الفيروس.",
                             "افحص الوجه السفلي للأوراق بحثًا عن الذباب الأبيض؛ والمصائد الصفراء اللاصقة تبيّن أعداده."]},
        "cultural": {"en": ["Raise transplants under insect-proof net (about 50 mesh) and use it on greenhouse openings.",
                            "Remove weeds and old crops that host whiteflies; leave a crop-free gap between seasons where possible."],
                     "ar": ["أنتج الشتلات تحت شباك مانعة للحشرات (حوالي 50 مش) واستخدمها على فتحات البيوت المحمية.",
                            "أزل الحشائش والمحاصيل القديمة التي تأوي الذباب الأبيض؛ واترك فترة خالية من المحصول بين المواسم متى أمكن."]},
        "chemical_groups": {"en": "Insecticides against whiteflies, rotating IRAC mode-of-action groups (whiteflies develop resistance "
                                  "quickly). They reduce spread but do not save already infected plants.",
                            "ar": "مبيدات حشرية ضد الذباب الأبيض مع التناوب بين مجموعات IRAC (يطوّر الذباب الأبيض المقاومة بسرعة). "
                                  "تقلل الانتشار لكنها لا تنقذ النباتات المصابة."},
        "prevention": {"en": ["Plant varieties resistant or tolerant to the virus (e.g. TYLCV-tolerant tomato, Ty genes)."],
                       "ar": ["ازرع أصنافًا مقاومة أو متحملة للفيروس (مثل أصناف الطماطم المتحملة لفيروس تجعد الأوراق الأصفر)."]},
        "sources": ["irac", "fao_gap_greenhouse"],
    },
    "virus_aphid": {
        "name": {"en": "Virus spread by aphids (and often seed) - no cure", "ar": "فيروس ينقله المنّ (وغالبًا البذور) - لا علاج له"},
        "immediate": {"en": ["There is no cure. Remove infected plants early in the season, before aphids carry the virus on.",
                             "Wash hands and tools after touching infected plants."],
                      "ar": ["لا يوجد علاج. أزل النباتات المصابة مبكرًا في الموسم قبل أن ينقل المنّ الفيروس.",
                             "اغسل يديك وأدواتك بعد لمس النباتات المصابة."]},
        "cultural": {"en": ["Aphids transmit these viruses within seconds of probing, so insecticides rarely stop spread; "
                            "barriers work better: floating row covers on young plants, reflective mulch, weed control around the field."],
                     "ar": ["ينقل المنّ هذه الفيروسات خلال ثوانٍ من الوخز، لذلك نادرًا ما توقف المبيدات الحشرية الانتشار؛ "
                            "الحواجز أفضل: أغطية الصفوف الخفيفة على النباتات الصغيرة، والغطاء العاكس، ومكافحة الحشائش حول الحقل."]},
        "chemical_groups": {"en": "Mineral-oil sprays can reduce this type of (non-persistent) transmission; insecticides "
                                  "(rotating IRAC groups) are for heavy aphid populations, not as the main virus control.",
                            "ar": "رش الزيوت المعدنية قد يقلل هذا النوع من النقل (غير المثابر)؛ والمبيدات الحشرية (بالتناوب بين مجموعات IRAC) "
                                  "للأعداد الكبيرة من المنّ فقط وليست الوسيلة الرئيسية لمكافحة الفيروس."},
        "prevention": {"en": ["Use certified virus-free seed and resistant varieties."],
                       "ar": ["استخدم بذورًا معتمدة خالية من الفيروس وأصنافًا مقاومة."]},
        "sources": ["irac"],
    },
    "virus_contact": {
        "name": {"en": "Virus spread by contact, tools and seed - no cure", "ar": "فيروس ينتقل باللمس والأدوات والبذور - لا علاج له"},
        "immediate": {"en": ["There is no cure. Remove infected plants and bag them.",
                             "Disinfect tools, stakes and hands (soap, or skim milk dips during handling); work on healthy plants before infected ones.",
                             "Do not smoke or handle tobacco near plants (tobamoviruses can survive in tobacco products)."],
                      "ar": ["لا يوجد علاج. أزل النباتات المصابة وضعها في أكياس.",
                             "عقّم الأدوات والدعامات واليدين (بالصابون، أو بغمسها في الحليب منزوع الدسم أثناء العمل)؛ واعمل على النباتات السليمة قبل المصابة.",
                             "لا تدخّن ولا تتعامل مع التبغ قرب النباتات (فيروسات التوباموفيرس قد تعيش في منتجات التبغ)."]},
        "cultural": {"en": ["Remove crop residues and roots; the virus survives in debris and soil for a long time."],
                     "ar": ["أزل بقايا المحصول والجذور؛ فالفيروس يعيش طويلًا في البقايا والتربة."]},
        "chemical_groups": None,
        "prevention": {"en": ["Use certified seed and resistant varieties (e.g. Tm-2² tomatoes for ToMV)."],
                       "ar": ["استخدم بذورًا معتمدة وأصنافًا مقاومة (مثل أصناف الطماطم الحاملة لجين Tm-2² ضد فيروس موزاييك الطماطم)."]},
        "sources": ["fao_gap_greenhouse"],
    },
    "virus_planting_material": {
        "name": {"en": "Virus carried in planting material (grafts, cuttings) - no cure", "ar": "فيروس ينتقل عبر مواد الإكثار (الطعوم والعُقل) - لا علاج له"},
        "immediate": {"en": ["There is no cure; mark the plant and watch whether neighbours develop symptoms.",
                             "Do not take cuttings or budwood from it."],
                      "ar": ["لا يوجد علاج؛ ضع علامة على النبات وراقب ظهور الأعراض على النباتات المجاورة.",
                             "لا تأخذ منه عُقلًا أو طعومًا."]},
        "cultural": {"en": ["Severely affected trees/vines that yield poorly are best replaced with certified virus-tested stock."],
                     "ar": ["الأشجار أو الكروم شديدة الإصابة ضعيفة الإنتاج يُفضَّل استبدالها بشتلات معتمدة مفحوصة من الفيروسات."]},
        "chemical_groups": None,
        "prevention": {"en": ["Buy certified, virus-tested nursery plants."], "ar": ["اشترِ شتلات معتمدة ومفحوصة من الفيروسات."]},
        "sources": [],
    },
    "mites": {
        "name": {"en": "Spider mites (pest)", "ar": "العنكبوت الأحمر (آفة)"},
        "immediate": {"en": ["Confirm with a hand lens: tiny moving mites and fine webbing on the leaf underside.",
                             "Remove heavily infested leaves; wash dust off plants (dust and heat favour mites)."],
                      "ar": ["تأكّد بعدسة مكبرة: حَلَم صغير جدًا متحرك ونسيج رفيع على الوجه السفلي للورقة.",
                             "أزل الأوراق شديدة الإصابة؛ واغسل الغبار عن النباتات (الغبار والحرارة يشجعان الحَلَم)."]},
        "cultural": {"en": ["Avoid water stress; keep dusty paths damp.",
                            "Avoid broad-spectrum insecticides (e.g. pyrethroids) that kill natural enemies and cause mite outbreaks.",
                            "In greenhouses, predatory mites (e.g. Phytoseiulus persimilis) give good biological control."],
                     "ar": ["تجنّب العطش؛ وحافظ على رطوبة الممرات المغبرة.",
                            "تجنّب المبيدات واسعة الطيف (مثل البيرثرويدات) التي تقتل الأعداء الطبيعية وتسبب تفشي الحَلَم.",
                            "في البيوت المحمية يعطي الحَلَم المفترس (مثل Phytoseiulus persimilis) مكافحة حيوية جيدة."]},
        "chemical_groups": {"en": "Acaricides from different IRAC groups in rotation (mites develop resistance within a few generations); "
                                  "spray the leaf undersides. Horticultural oils or insecticidal soaps for light infestations.",
                            "ar": "مبيدات أكاروسية من مجموعات IRAC مختلفة بالتناوب (يطوّر الحَلَم المقاومة خلال أجيال قليلة)؛ ورشّ الوجه السفلي للأوراق. "
                                  "الزيوت الزراعية أو الصابون الزراعي للإصابات الخفيفة."},
        "prevention": {"en": ["Scout weekly in hot, dry months; act on the first colonies."],
                       "ar": ["افحص أسبوعيًا في الأشهر الحارة الجافة؛ وتصرّف عند ظهور أول المستعمرات."]},
        "sources": ["irac"],
    },
    "bacterial_wilt_vector": {
        "name": {"en": "Bacterial wilt spread by cucumber beetles - no cure", "ar": "ذبول بكتيري تنقله خنافس الخيار - لا علاج له"},
        "immediate": {"en": ["Wilted plants do not recover: remove and bag them.",
                             "Look for striped or spotted cucumber beetles on young plants and flowers."],
                      "ar": ["النباتات الذابلة لا تتعافى: أزلها وضعها في أكياس.",
                             "ابحث عن خنافس الخيار المخططة أو المنقطة على النباتات الصغيرة والأزهار."]},
        "cultural": {"en": ["Protect young plants with row covers until flowering (then remove for pollination)."],
                     "ar": ["احمِ النباتات الصغيرة بأغطية الصفوف حتى التزهير (ثم أزلها للتلقيح)."]},
        "chemical_groups": {"en": "Insecticides against cucumber beetles early in the season (rotate IRAC groups); there is no bactericide that cures the wilt.",
                            "ar": "مبيدات حشرية ضد خنافس الخيار مبكرًا في الموسم (بالتناوب بين مجموعات IRAC)؛ ولا يوجد مبيد بكتيري يعالج الذبول."},
        "prevention": {"en": ["Early beetle control is the only effective prevention."], "ar": ["مكافحة الخنافس مبكرًا هي الوقاية الفعالة الوحيدة."]},
        "sources": ["irac"],
    },
    "smut": {
        "name": {"en": "Smut (fungal galls)", "ar": "التفحم (أورام فطرية)"},
        "immediate": {"en": ["Cut off galls before they break open and release black spores; bag and remove them."],
                      "ar": ["اقطع الأورام قبل أن تنفجر وتطلق الجراثيم السوداء؛ وضعها في أكياس وأخرجها من الحقل."]},
        "cultural": {"en": ["Avoid injuring plants (cultivation, hail, insects) and excess nitrogen; rotate crops."],
                     "ar": ["تجنّب جرح النباتات (العزيق، البَرَد، الحشرات) والإفراط في النيتروجين؛ واتبع دورة زراعية."]},
        "chemical_groups": None,
        "prevention": {"en": ["Fungicides are not effective; use less susceptible hybrids."],
                       "ar": ["المبيدات الفطرية غير فعالة؛ استخدم هجنًا أقل قابلية للإصابة."]},
        "sources": [],
    },
    "trunk_disease": {
        "name": {"en": "Grapevine trunk disease (wood-infecting fungi)", "ar": "مرض خشب الكرمة (فطريات تصيب الخشب)"},
        "immediate": {"en": ["Leaf symptoms come from infection inside the wood; sprays on the leaves do not cure it.",
                             "Mark affected vines; in the dormant season cut back to healthy wood and remove the prunings from the vineyard."],
                      "ar": ["أعراض الأوراق ناتجة عن إصابة داخل الخشب؛ والرش على الأوراق لا يعالجها.",
                             "ضع علامة على الكروم المصابة؛ وفي موسم السكون قلّم حتى الخشب السليم وأخرج مخلفات التقليم من الكرم."]},
        "cultural": {"en": ["Prune in dry weather and late in the dormant season; protect large pruning wounds."],
                     "ar": ["قلّم في الجو الجاف وفي أواخر موسم السكون؛ واحمِ جروح التقليم الكبيرة."]},
        "chemical_groups": {"en": "Pruning-wound protectants registered for grapevine trunk diseases, applied right after pruning.",
                            "ar": "مواد حماية جروح التقليم المسجلة لأمراض خشب العنب، تُطبّق مباشرة بعد التقليم."},
        "prevention": {"en": ["Start new plantings with clean, certified nursery vines."], "ar": ["ابدأ الزراعات الجديدة بشتلات نظيفة معتمدة."]},
        "sources": [],
    },
}
