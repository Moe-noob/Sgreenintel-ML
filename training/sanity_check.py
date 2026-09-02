from dataset import get_datasets, get_class_weights, get_class_names

train_ds, val_ds, test_ds = get_datasets()

print(f"Train: {len(train_ds)} images")
print(f"Val:   {len(val_ds)} images")
print(f"Test:  {len(test_ds)} images")
print(f"Classes ({len(train_ds.classes)}):")
for name in get_class_names(train_ds):
    print(f"  {name}")

weights = get_class_weights(train_ds)
print(f"\nClass weights (first 5): {weights[:5]}")