# Where did the benchmark photos go?

- Official test photos (PlantDoc test + PlantWild test, mapped labels): **1385**
- Kept in the frozen benchmark: **1267** (91.5%)
- dropped: label conflict: **98** (7.1%)
- dropped: class excluded: **20** (1.4%)
- dropped: other: **0** (0.0%)

- Effective benchmark size, counting near-copies once: **1261** of 1267 photos (12 photos share a duplicate group)

| Source | Official test | Kept | Label conflict | Class excluded |
|---|---|---|---|---|
| plantdoc | 236 | 215 | 15 | 6 |
| plantwild_v1 | 1149 | 1052 | 83 | 14 |

| Class | Official test | Kept | Label conflict | Class excluded |
|---|---|---|---|---|
| _unsupported | 45 | 45 | 0 | 0 |
| apple__black_rot | 34 | 33 | 1 | 0 |
| apple__cedar_apple_rust | 71 | 68 | 3 | 0 |
| apple__healthy | 97 | 97 | 0 | 0 |
| apple__scab | 68 | 65 | 3 | 0 |
| bell_pepper__bacterial_spot | 32 | 31 | 1 | 0 |
| bell_pepper__healthy | 56 | 55 | 1 | 0 |
| corn__common_rust | 57 | 57 | 0 | 0 |
| corn__gray_leaf_spot | 47 | 39 | 8 | 0 |
| corn__healthy | 31 | 31 | 0 | 0 |
| corn__northern_leaf_blight | 56 | 47 | 9 | 0 |
| grape__black_rot | 53 | 52 | 1 | 0 |
| grape__healthy | 52 | 52 | 0 | 0 |
| potato__early_blight | 53 | 44 | 9 | 0 |
| potato__healthy | 49 | 49 | 0 | 0 |
| potato__late_blight | 56 | 47 | 9 | 0 |
| squash__powdery_mildew | 6 | 0 | 0 | 6 |
| strawberry__healthy | 47 | 47 | 0 | 0 |
| strawberry__leaf_scorch | 15 | 0 | 1 | 14 |
| tomato__bacterial_spot | 65 | 56 | 9 | 0 |
| tomato__early_blight | 78 | 65 | 13 | 0 |
| tomato__healthy | 53 | 51 | 2 | 0 |
| tomato__late_blight | 69 | 56 | 13 | 0 |
| tomato__leaf_curl_virus | 40 | 37 | 3 | 0 |
| tomato__leaf_mold | 53 | 51 | 2 | 0 |
| tomato__mosaic_virus | 47 | 45 | 2 | 0 |
| tomato__septoria_leaf_spot | 55 | 47 | 8 | 0 |

Most common label conflicts among dropped test photos:

- corn__gray_leaf_spot vs corn__northern_leaf_blight: 15
- potato__early_blight vs potato__late_blight: 10
- potato__early_blight vs tomato__early_blight: 8
- tomato__early_blight vs tomato__late_blight: 7
- tomato__early_blight vs tomato__septoria_leaf_spot: 6
- apple__cedar_apple_rust vs apple__scab: 5
- potato__late_blight vs tomato__late_blight: 5
- tomato__bacterial_spot vs tomato__septoria_leaf_spot: 5
- tomato__leaf_curl_virus vs tomato__mosaic_virus: 5
- tomato__bacterial_spot vs tomato__late_blight: 4
