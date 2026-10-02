# v1 (mobilenetv2_sgreenintel_v6p2.pth) — test split

Photos: 1267 (supported classes this model knows: 1222; photos of classes unknown to this model: 0.0%)

| Mode | Accuracy (95 % CI) | Macro-F1 (95 % CI) | ECE | Accepted share | Accuracy on accepted |
|---|---|---|---|---|---|
| Model picks crop and disease | 67.0% (64.6%–69.7%) | 65.5% (62.5%–68.1%) | 0.158 | 73.9% | 76.9% |
| Crop selected by user | 76.5% (74.3%–78.9%) | 75.3% (72.7%–77.6%) | 0.111 | 81.3% | 83.5% |

| Crop | Accuracy | Photos |
|---|---|---|
| apple | 66.9% | 263 |
| bell_pepper | 64.0% | 86 |
| corn | 73.6% | 174 |
| grape | 93.3% | 104 |
| potato | 65.7% | 140 |
| strawberry | 89.4% | 47 |
| tomato | 56.1% | 408 |

| Class | Precision | Recall | F1 | Photos |
|---|---|---|---|---|
| apple__black_rot | 0.48 | 0.39 | 0.43 | 33 |
| apple__cedar_apple_rust | 0.80 | 0.84 | 0.82 | 68 |
| apple__healthy | 0.74 | 0.68 | 0.71 | 97 |
| apple__scab | 0.78 | 0.62 | 0.69 | 65 |
| bell_pepper__bacterial_spot | 0.52 | 0.45 | 0.48 | 31 |
| bell_pepper__healthy | 0.73 | 0.75 | 0.74 | 55 |
| corn__common_rust | 0.89 | 0.88 | 0.88 | 57 |
| corn__gray_leaf_spot | 0.61 | 0.36 | 0.45 | 39 |
| corn__healthy | 0.71 | 0.87 | 0.78 | 31 |
| corn__northern_leaf_blight | 0.64 | 0.79 | 0.70 | 47 |
| grape__black_rot | 0.74 | 0.94 | 0.83 | 52 |
| grape__healthy | 0.80 | 0.92 | 0.86 | 52 |
| potato__early_blight | 0.68 | 0.43 | 0.53 | 44 |
| potato__healthy | 0.50 | 0.84 | 0.63 | 49 |
| potato__late_blight | 0.76 | 0.68 | 0.72 | 47 |
| strawberry__healthy | 0.91 | 0.89 | 0.90 | 47 |
| tomato__bacterial_spot | 0.55 | 0.30 | 0.39 | 56 |
| tomato__early_blight | 0.59 | 0.63 | 0.61 | 65 |
| tomato__healthy | 0.74 | 0.73 | 0.73 | 51 |
| tomato__late_blight | 0.56 | 0.61 | 0.58 | 56 |
| tomato__leaf_curl_virus | 0.62 | 0.41 | 0.49 | 37 |
| tomato__leaf_mold | 0.69 | 0.75 | 0.72 | 51 |
| tomato__mosaic_virus | 0.48 | 0.44 | 0.46 | 45 |
| tomato__septoria_leaf_spot | 0.56 | 0.57 | 0.57 | 47 |