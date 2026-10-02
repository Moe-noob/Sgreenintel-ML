# v1 on the frozen benchmark: contamination check

Predictions: `feature1_eval\work\eval_mobilenetv2_sgreenintel_v6p2\test\predictions.csv`

- Benchmark photos: **1267**; with a near-duplicate in v1's training data: **83** (6.6%)

  - plantdoc: 20 of 215
  - plantwild_v1: 63 of 1052

| Mode | Photos | n | Accuracy | 95% interval |
|---|---|---|---|---|
| auto | all | 1222 | 67.0% | 64.3-69.6% |
| auto | clean | 1140 | 65.3% | 62.5-68.0% |
| auto | contaminated | 82 | 91.5% | 83.4-95.8% |
| crop_given | all | 1222 | 76.5% | 74.1-78.8% |
| crop_given | clean | 1140 | 75.2% | 72.6-77.6% |
| crop_given | contaminated | 82 | 95.1% | 88.1-98.1% |

Only photos of classes v1 can predict are counted. 'Clean' photos have no near-duplicate (pHash distance <= 6 of 64 bits) among the images v1 trained on, so the clean row is the fairest estimate of v1's accuracy on unseen field photos. A large gap between clean and contaminated rows means the reported score was inflated.
