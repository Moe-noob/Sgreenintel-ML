"""
Interactive Plotly map: our 99-cell ETc grid, geometrically clipped to
Saudi Arabia's real national border (not just filtered by cell center),
so coastal/edge cells follow the true coastline instead of staying full
rectangles. Rendered with Choroplethmap. The 13 official administrative
regions are overlaid as outline boundaries.
"""

import json
from pathlib import Path
from shapely.geometry import shape, box, mapping, Point
from shapely.ops import unary_union
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "heatmap_results.json"
BORDER_PATH = PROJECT_ROOT / "data" / "geo" / "national_border" / "SAU-geo.json"
REGIONS_PATH = PROJECT_ROOT / "data" / "geo" / "GeoJSON-of-Saudi-Arabia-Regions" / "data" / "SA_regions.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "heatmap_visualization_v2.html"

MONTH = "JUL"
CROPS = ["Tomato", "Potato", "Pepper,_bell", "Grape", "Apple", "Corn_(maize)"]


def load_border_polygon():
    with open(BORDER_PATH) as f:
        border_geojson = json.load(f)
    geoms = [shape(f["geometry"]) for f in border_geojson["features"]]
    return unary_union(geoms)


def load_region_outlines():
    with open(REGIONS_PATH) as f:
        return json.load(f)


def filter_cells_inside_border(data, border_polygon):
    """First-pass filter by center point, before geometric clipping."""
    kept = {}
    dropped_count = 0
    for cell_id, cell in data.items():
        point = Point(cell["center_lon"], cell["center_lat"])
        if border_polygon.contains(point):
            kept[cell_id] = cell
        else:
            dropped_count += 1
    return kept, dropped_count


def build_clipped_grid_geojson(data, border_polygon):
    """Clips each cell rectangle to the actual Saudi border shape, so
    coastal cells follow the real coastline instead of staying full
    squares. Returns the geojson plus the ordered list of cell_ids that
    survived clipping (should match input, but handled defensively)."""
    features = []
    kept_ids = []

    for cell_id, cell in data.items():
        b = cell["bounds"]
        cell_box = box(b["lon_min"], b["lat_min"], b["lon_max"], b["lat_max"])
        clipped = cell_box.intersection(border_polygon)

        if clipped.is_empty:
            continue

        features.append({
            "type": "Feature",
            "id": cell_id,
            "properties": {"cell_id": cell_id},
            "geometry": mapping(clipped),
        })
        kept_ids.append(cell_id)

    return {"type": "FeatureCollection", "features": features}, kept_ids


def build_traces(data, border_polygon):
    grid_geojson, ordered_ids = build_clipped_grid_geojson(data, border_polygon)
    traces = []

    for crop in CROPS:
        locations, z_values, hover_texts = [], [], []
        for cell_id in ordered_ids:
            cell = data[cell_id]
            month_data = cell["monthly"][MONTH]
            etc = month_data["crops"][crop]["etc_mm_day"]
            climate = month_data["climate"]

            locations.append(cell_id)
            z_values.append(etc)
            hover_texts.append(
                f"<b>{crop} ETc: {etc} mm/day</b><br>"
                f"Temp: {climate['temp_c']}°C, Humidity: {climate['humidity_pct']}%<br>"
                f"Precip: {climate['precip_mm_day']} mm/day"
            )

        traces.append(go.Choroplethmap(
            geojson=grid_geojson,
            locations=locations,
            z=z_values,
            text=hover_texts,
            hoverinfo="text",
            colorscale="YlOrRd",
            colorbar=dict(title="ETc (mm/day)"),
            zmin=min(z_values), zmax=max(z_values),
            marker_line_width=0.3,
            marker_line_color="rgba(0,0,0,0.2)",
            marker_opacity=0.35,
            visible=(crop == CROPS[0]),
        ))
    return traces


def build_dropdown_buttons(traces, n_extra_traces):
    buttons = []
    for i, crop in enumerate(CROPS):
        visibility = [j == i for j in range(len(traces) - n_extra_traces)] + [True] * n_extra_traces
        buttons.append(dict(
            label=crop.replace("_", " ").replace(",", ""),
            method="update",
            args=[{"visible": visibility},
                  {"title": f"Saudi Arabia — {crop.replace('_', ' ')} Water Requirement (ETc), {MONTH}"}],
        ))
    return buttons


def main():
    border_polygon = load_border_polygon()
    region_outlines = load_region_outlines()

    with open(RESULTS_PATH) as f:
        data = json.load(f)

    filtered_data, dropped = filter_cells_inside_border(data, border_polygon)
    print(f"Kept {len(filtered_data)}/{len(data)} cells inside Saudi Arabia's border ({dropped} dropped)")

    crop_traces = build_traces(filtered_data, border_polygon)

    outline_trace = go.Choroplethmap(
        geojson=region_outlines,
        locations=[f["properties"]["name"] for f in region_outlines["features"]],
        z=[0] * len(region_outlines["features"]),
        featureidkey="properties.name",
        showscale=False,
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
        marker_line_color="black",
        marker_line_width=1.5,
        marker_opacity=0,
        hoverinfo="skip",
    )

    all_traces = crop_traces + [outline_trace]
    buttons = build_dropdown_buttons(all_traces, n_extra_traces=1)

    fig = go.Figure(data=all_traces)
    fig.update_layout(
        title=f"Saudi Arabia — {CROPS[0].replace('_', ' ')} Water Requirement (ETc), {MONTH}",
        map=dict(
            style="open-street-map",
            center=dict(lat=24, lon=45),
            zoom=4.2,
        ),
        updatemenus=[dict(
            active=0, buttons=buttons, direction="down",
            x=0.02, y=0.98, xanchor="left", yanchor="top",
        )],
        margin=dict(l=0, r=0, t=60, b=0), height=750,
    )

    fig.write_html(str(OUTPUT_PATH))
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()