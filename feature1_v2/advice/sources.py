"""
Bibliography for the advice knowledge base. Every advice entry cites keys
from here. URLs are the publishers' landing pages; they could not be opened
from the build environment (no internet), so each one must be checked
during expert review (see review_status in kb.py).
"""

SOURCES = {
    # --- management guidelines (extension) ---
    "ucipm_tomato": ("UC IPM Pest Management Guidelines: Tomato", "University of California Agriculture and Natural Resources", "https://ipm.ucanr.edu/agriculture/tomato/"),
    "ucipm_potato": ("UC IPM Pest Management Guidelines: Potato", "University of California ANR", "https://ipm.ucanr.edu/agriculture/potato/"),
    "ucipm_pepper": ("UC IPM Pest Management Guidelines: Peppers", "University of California ANR", "https://ipm.ucanr.edu/agriculture/peppers/"),
    "ucipm_cucurbits": ("UC IPM Pest Management Guidelines: Cucurbits", "University of California ANR", "https://ipm.ucanr.edu/agriculture/cucurbits/"),
    "ucipm_grape": ("UC IPM Pest Management Guidelines: Grape", "University of California ANR", "https://ipm.ucanr.edu/agriculture/grape/"),
    "ucipm_strawberry": ("UC IPM Pest Management Guidelines: Strawberry", "University of California ANR", "https://ipm.ucanr.edu/agriculture/strawberry/"),
    "ucipm_lettuce": ("UC IPM Pest Management Guidelines: Lettuce", "University of California ANR", "https://ipm.ucanr.edu/agriculture/lettuce/"),
    "ucipm_cole": ("UC IPM Pest Management Guidelines: Cole Crops", "University of California ANR", "https://ipm.ucanr.edu/agriculture/cole-crops/"),
    "ucipm_corn": ("UC IPM Pest Management Guidelines: Corn", "University of California ANR", "https://ipm.ucanr.edu/agriculture/corn/"),
    "ucipm_beans": ("UC IPM Pest Management Guidelines: Dry Beans", "University of California ANR", "https://ipm.ucanr.edu/agriculture/dry-beans/"),
    "ucipm_onion": ("UC IPM Pest Management Guidelines: Onion and Garlic", "University of California ANR", "https://ipm.ucanr.edu/agriculture/onion-and-garlic/"),
    "ucipm_apple": ("UC IPM Pest Management Guidelines: Apple", "University of California ANR", "https://ipm.ucanr.edu/agriculture/apple/"),
    "fao_gap_greenhouse": ("Good Agricultural Practices for greenhouse vegetable crops: principles for Mediterranean climate areas (FAO Plant Production and Protection Paper 217, 2013)", "FAO", "https://www.fao.org/4/i3284e/i3284e.pdf"),
    # --- reference compendia (symptoms, look-alikes) ---
    "aps_tomato": ("Compendium of Tomato Diseases and Pests, 2nd ed. (Jones, Zitter, Momol, Miller, 2014)", "APS Press", "https://apsjournals.apsnet.org/doi/book/10.1094/9780890544341"),
    "aps_cucurbit": ("Compendium of Cucurbit Diseases and Pests, 2nd ed. (Keinath, Wintermantel, Zitter, 2017)", "APS Press", "https://apsjournals.apsnet.org/doi/book/10.1094/9780890545744"),
    "aps_potato": ("Compendium of Potato Diseases, 2nd ed. (Stevenson, Loria, Franc, Weingartner, 2001)", "APS Press", "https://www.apsnet.org/"),
    "aps_grape": ("Compendium of Grape Diseases, Disorders, and Pests, 2nd ed. (Wilcox, Gubler, Uyemoto, 2015)", "APS Press", "https://apsjournals.apsnet.org/doi/book/10.1094/9780890544815"),
    "aps_corn": ("Compendium of Corn Diseases, 4th ed. (Munkvold, White, 2016)", "APS Press", "https://apsjournals.apsnet.org/doi/book/10.1094/9780890544945"),
    "aps_apple": ("Compendium of Apple and Pear Diseases and Pests, 2nd ed. (Sutton, Aldwinckle, Agnello, Walgenbach, 2014)", "APS Press", "https://apsjournals.apsnet.org/doi/book/10.1094/9780890544433"),
    "aps_strawberry": ("Compendium of Strawberry Diseases, 2nd ed. (Maas, 1998)", "APS Press", "https://www.apsnet.org/"),
    "aps_lettuce": ("Compendium of Lettuce Diseases and Pests, 2nd ed. (Subbarao, Davis, Gilbertson, Raid, 2017)", "APS Press", "https://www.apsnet.org/"),
    "aps_brassica": ("Compendium of Brassica Diseases (Rimmer, Shattuck, Buchwaldt, 2007)", "APS Press", "https://www.apsnet.org/"),
    "aps_bean": ("Compendium of Bean Diseases, 2nd ed. (Schwartz, Steadman, Hall, Forster, 2005)", "APS Press", "https://www.apsnet.org/"),
    "aps_onion": ("Compendium of Onion and Garlic Diseases and Pests, 2nd ed. (Schwartz, Mohan, 2008)", "APS Press", "https://www.apsnet.org/"),
    "aps_pepper": ("Compendium of Pepper Diseases (Pernezny, Roberts, Murphy, Goldberg, 2003)", "APS Press", "https://www.apsnet.org/"),
    # --- pesticide resistance management (mode-of-action groups) ---
    "frac": ("FRAC Code List: fungal control agents sorted by cross-resistance pattern and mode of action", "Fungicide Resistance Action Committee", "https://www.frac.info/"),
    "irac": ("IRAC Mode of Action Classification Scheme", "Insecticide Resistance Action Committee", "https://irac-online.org/"),
    "mewa": ("Pesticide registration and agricultural extension services, Kingdom of Saudi Arabia", "Ministry of Environment, Water and Agriculture (MEWA)", "https://www.mewa.gov.sa/"),
    # --- weather rules ---
    "hutton": ("Dancey, Skelsey, Cooke (2017) The Hutton Criteria: a classification tool for identifying high risk periods for potato late blight disease development in Great Britain. EuroBlight workshop proceedings, PAGV Special Report 18 (page numbers to be checked)", "EuroBlight", "https://agro.au.dk/forskning/internationale-platforme/euroblight/"),
    "rule_10_10_24": ("Baldacci (1947) 'three tens' (10 degC, 10 mm rain, 10 cm shoots; also called 10-10-24) primary-infection rule for grapevine downy mildew, as reviewed in Gessler, Pertot, Perazzolli (2011) Plasmopara viticola: a review of knowledge on downy mildew of grapevine and effective disease management. Phytopathologia Mediterranea 50: 3-44", "Phytopathologia Mediterranea", "https://doi.org/10.14601/Phytopathol_Mediterr-9360"),
}


def cite(key):
    title, publisher, url = SOURCES[key]
    return {"key": key, "title": title, "publisher": publisher, "url": url}
