"""
Interactive Plotly map of Saudi Arabia's crop water requirement (ETc)
heatmap. Renders as a standalone HTML file — open it in any browser,
no server needed. Includes a dropdown to switch between crops.

Chosen default: July (peak summer heat, most illustrative contrast
between interior desert and coastal humid zones — e.g. Riyadh vs Jazan,
as validated in our spot-check).
"""

import json
from pathlib import Path
import plotly.graph_objects as go

RESULTS_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "heatmap_results.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "heatmap_visualization.html"

MONTH = "JUL"  # peak season — most illustrative
CROPS = ["Tomato", "Potato", "Pepper,_bell", "Grape", "Apple", "Corn_(maize)"]


def load_results():
    with open(RESULTS_PATH) as f:
        return json.load(f)


def build_traces(data):
    """One trace per crop, only the first visible by default — the
    dropdown menu toggles between them."""
    traces = []

    for crop in CROPS:
        lats, lons, etc_values, hover_texts = [], [], [], []

        for cell in data.values():
            month_data = cell["monthly"][MONTH]
            etc = month_data["crops"][crop]["etc_mm_day"]
            climate = month_data["climate"]

            lats.append(cell["center_lat"])
            lons.append(cell["center_lon"])
            etc_values.append(etc)
            hover_texts.append(
                f"Cell {cell['cell_id']}<br>"
                f"Lat/Lon: {cell['center_lat']}, {cell['center_lon']}<br>"
                f"<b>{crop} ETc: {etc} mm/day</b><br>"
                f"Temp: {climate['temp_c']}°C<br>"
                f"Humidity: {climate['humidity_pct']}%<br>"
                f"Precip: {climate['precip_mm_day']} mm/day"
            )

        traces.append(go.Scattergeo(
            lat=lats,
            lon=lons,
            text=hover_texts,
            hoverinfo="text",
            marker=dict(
                size=22,
                color=etc_values,
                colorscale="YlOrRd",  # yellow (low need) -> red (high need)
                colorbar=dict(title="ETc (mm/day)"),
                cmin=min(etc_values),
                cmax=max(etc_values),
                symbol="square",
                line=dict(width=0.5, color="black"),
            ),
            name=crop,
            visible=(crop == CROPS[0]),  # only first crop shown initially
        ))

    return traces


def build_dropdown_buttons(traces):
    buttons = []
    for i, crop in enumerate(CROPS):
        visibility = [j == i for j in range(len(traces))]
        buttons.append(dict(
            label=crop.replace("_", " ").replace(",", ""),
            method="update",
            args=[{"visible": visibility},
                  {"title": f"Saudi Arabia — {crop.replace('_', ' ')} Water Requirement (ETc), {MONTH}"}],
        ))
    return buttons


def main():
    data = load_results()
    traces = build_traces(data)
    buttons = build_dropdown_buttons(traces)

    fig = go.Figure(data=traces)

    fig.update_layout(
        title=f"Saudi Arabia — {CROPS[0].replace('_', ' ')} Water Requirement (ETc), {MONTH}",
        geo=dict(
            scope="asia",
            resolution=50,
            showcountries=True,
            countrycolor="black",
            showland=True,
            landcolor="rgb(240, 240, 230)",
            center=dict(lat=24, lon=45),
            projection_scale=4,
            lataxis_range=[14, 34],
            lonaxis_range=[33, 58],
        ),
        updatemenus=[dict(
            active=0,
            buttons=buttons,
            direction="down",
            x=0.02, y=0.98,
            xanchor="left", yanchor="top",
        )],
        margin=dict(l=0, r=0, t=60, b=0),
        height=700,
    )

    fig.write_html(str(OUTPUT_PATH))
    print(f"Saved interactive map to: {OUTPUT_PATH}")
    print("Open this file in any browser to view it.")


if __name__ == "__main__":
    main()