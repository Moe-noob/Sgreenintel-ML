from pathlib import Path
from collections import defaultdict

split_file = Path('data/raw/plantwild/plantwild/trainval.txt')
lines = split_file.read_text().splitlines()

NEEDED = {
    'apple black rot', 'apple leaf', 'apple rust', 'apple scab',
    'bell pepper leaf', 'bell pepper leaf spot',
    'corn gray leaf spot', 'corn leaf', 'corn northern leaf blight', 'corn rust',
    'grape black rot', 'grape leaf',
    'potato early blight', 'potato late blight', 'potato leaf',
    'strawberry leaf', 'strawberry leaf scorch',
    'tomato bacterial leaf spot', 'tomato early blight', 'tomato late blight',
    'tomato leaf', 'tomato leaf mold', 'tomato mosaic virus',
    'tomato septoria leaf spot', 'tomato yellow leaf curl virus',
}

counts = defaultdict(lambda: {'train': 0, 'val': 0, 'test': 0})
split_map = {0: 'test', 1: 'train', 2: 'val'}

for line in lines:
    parts = line.strip().split('=')
    if len(parts) != 3:
        continue
    img_path, class_idx, split_idx = parts
    class_name = img_path.split('/')[0]
    if class_name in NEEDED:
        split_name = split_map.get(int(split_idx), 'unknown')
        counts[class_name][split_name] += 1

print(f"{'Class':<40s} {'Train':>6} {'Val':>5} {'Test':>5} {'Total':>6}")
print('-' * 62)
total_train = total_val = total_test = 0
for cls in sorted(counts.keys()):
    c = counts[cls]
    t = c['train'] + c['val'] + c['test']
    print(f"{cls:<40s} {c['train']:>6} {c['val']:>5} {c['test']:>5} {t:>6}")
    total_train += c['train']
    total_val += c['val']
    total_test += c['test']
print('-' * 62)
total = total_train + total_val + total_test
print(f"{'TOTAL':<40s} {total_train:>6} {total_val:>5} {total_test:>5} {total:>6}")
