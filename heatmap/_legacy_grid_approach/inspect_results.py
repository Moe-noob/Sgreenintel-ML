import json

with open('data/processed/heatmap_results.json') as f:
    data = json.load(f)

print(f'Total cells: {len(data)}')
print()

closest = min(data.values(), key=lambda c: (c['center_lat']-24.71)**2 + (c['center_lon']-46.68)**2)
print(f"Closest cell to Riyadh: cell {closest['cell_id']} at ({closest['center_lat']}, {closest['center_lon']})")
print()

print('July data for that cell:')
july = closest['monthly']['JUL']
print(f"  ET0: {july['et0_mm_day']} mm/day")
print(f"  Temp: {july['climate']['temp_c']}C, Precip: {july['climate']['precip_mm_day']}mm/day")
for crop, vals in july['crops'].items():
    print(f"    {crop}: ETc = {vals['etc_mm_day']} mm/day")

jazan_like = min(data.values(), key=lambda c: (c['center_lat']-16.9)**2 + (c['center_lon']-42.5)**2)
print(f"\nClosest cell to Jazan (south, coastal): cell {jazan_like['cell_id']} at ({jazan_like['center_lat']}, {jazan_like['center_lon']})")
print('July data for that cell:')
july_j = jazan_like['monthly']['JUL']
print(f"  ET0: {july_j['et0_mm_day']} mm/day")
print(f"  Temp: {july_j['climate']['temp_c']}C, Humidity: {july_j['climate']['humidity_pct']}%, Precip: {july_j['climate']['precip_mm_day']}mm/day")