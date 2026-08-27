# -*- coding: utf-8 -*-
import pandas as pd
import folium
from folium import plugins
from math import radians, cos, sin, asin, sqrt
import json
import time


BIZ_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTnw8aY-ILuZ7TqXjZ-BV3e5kPGRRXc7gUP9Fl5IhCbU09wNsLLo2UaF58X1oeRmV6c6CyafaXHSadS/pub?gid=1757974503&single=true&output=csv"
VAC_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRPyO2Ma_4KIm7kcQjpvSNgyzOmtQ0zN6KFwzQxd5ZUNOhOcOLUEKmAqeWdjfK-lMrbSuC5ZQri73aW/pub?gid=625158385&single=true&output=csv"

CACHE_BUST = f"&_cb={int(time.time())}"

biz = pd.read_csv(BIZ_SHEET_URL + CACHE_BUST)
vac = pd.read_csv(VAC_SHEET_URL + CACHE_BUST)

biz = biz.dropna(subset=["lat", "lng"])
vac = vac.dropna(subset=["lat", "lng"])

# Colors
PURPLE  = "#625D9C"
GREEN   = "#6CCA98"
NAVY    = "#00205C"
LILAC   = "#8B86C4"
MINT    = "#A8E6C8"
CORAL   = "#E8622A"
GOLD    = "#F0A500"
SLATE   = "#4A5568"
VAC_RED = "#E53935"

# Icon + colour per Business Type
type_styles = {
    "Cafe":        {"icon": "fa-coffee",        "color": "#7B5EA7"},
    "F&B":         {"icon": "fa-utensils",      "color": "#615378"},
    "Retail":      {"icon": "fa-shopping-bag",  "color": PURPLE},
    "Hospitality": {"icon": "fa-hotel",         "color": NAVY},
    "Services":    {"icon": "fa-concierge-bell","color": "#7047b5"},
    "GF Office":   {"icon": "fa-briefcase",     "color": "#9c76db"},
    "Residential": {"icon": "fa-home",          "color": LILAC},
    "Other":       {"icon": "fa-circle",        "color": SLATE},
}

cat_styles = {
    "Bar":                  {"icon": "fa-cocktail",    "color": LILAC},
    "Hotel":                {"icon": "fa-hotel",       "color": NAVY},
    "Beauty & Personal Care": {"icon": "fa-spa",       "color": "#A78BCA"},
    "Healthcare & Wellness":  {"icon": "fa-heartbeat",  "color": "#9B7FC7"},
}

def get_style(row):
    cat   = str(row.get("Category", "")).strip()
    btype = str(row.get("Business Type", "")).strip()
    if cat in cat_styles:
        return cat_styles[cat]
    return type_styles.get(btype, type_styles["Other"])

def haversine(lat1, lng1, lat2, lng2):
    R = 3958.8
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    a = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lng2-lng1)/2)**2
    return R * 2 * asin(sqrt(a))

key_types = ["Cafe", "F&B", "Retail", "Hospitality", "Services", "GF Office", "Residential"]

# Tenant opportunity groups
opportunity_groups = {
    "Cafe / Coffee": [
        "Cafe"
    ],
    "Restaurant": [
        "American", "Italian", "Japanese", "Thai", "Mexican",
        "Vietnamese", "Yemeni", "Greek", "Nepalese",
        "Asian Fusion", "Portuguese", "French", "Mediterranean",
        "Peruvian", "Latin American", "Taiwanese", "Hawaiian",
        "Korean", "Ukrainian", "Middle Eastern", "German", "Chinese",
        "Other food", "Irish"
    ],
    "Bar": [
        "Bar"
    ],
    "Fashion & Retail": [
        "Fashion & Accessories"
        ],
    "Personal Care Services": [
        "Beauty & Personal Care", "Health & Beauty"
        ],
    "Home / Living Retail": [
        "Home & Living", "Recreational Goods", "Convenience & Everyday Essentials", "Books & Media"
    ],
    "Arts & Culture / Experience": [
        "Arts & Culture", "Event Venue"
    ],
    "Offices / Services": [
        "Financial & Legal", "Financial Services", "Legal Services",
        "Real Estate", "Public Relations", "Creative", "Corporate",
        "VC", "Tech and AI", "Nonprofit"
    ],
    "Visitor-Serving Use": [
        "Hotel", "Attraction", "Public Space"
    ]
}

type_colors_js = {
    "Cafe":        "#7B5EA7",
    "F&B":         "#615378",
    "Retail":      PURPLE,
    "Hospitality": NAVY,
    "Services":    "#7047b5",
    "GF Office":   "#9c76db",
    "Residential": LILAC,
}

def count_categories_within(vlat, vlng, miles):
    nearby = biz[biz.apply(
        lambda r: haversine(vlat, vlng, r["lat"], r["lng"]) <= miles, axis=1
    )]

    if "Category" not in nearby.columns or len(nearby) == 0:
        return {}, 0

    counts = nearby["Category"].dropna().astype(str).str.strip().value_counts().to_dict()
    return counts, len(nearby)

def group_count(cat_counts, categories):
    return sum(cat_counts.get(c, 0) for c in categories)

def get_primary_secondary_opportunities(vlat, vlng):
    counts_005, total_005 = count_categories_within(vlat, vlng, 0.05)
    counts_010, total_010 = count_categories_within(vlat, vlng, 0.10)
    counts_015, total_015 = count_categories_within(vlat, vlng, 0.15)

    scored = []

    for group_name, cats in opportunity_groups.items():
        c005 = group_count(counts_005, cats)
        c010 = group_count(counts_010, cats)
        c015 = group_count(counts_015, cats)

        score = 0

        if c005 == 0:
            score += 2
        elif c005 == 1:
            score += 1

        if c010 == 0:
            score += 3
        elif c010 <= 2:
            score += 2
        elif c010 <= 4:
            score += 1

        if c015 == 0:
            score += 4
        elif c015 <= 3:
            score += 3
        elif c015 <= 6:
            score += 2

        if c005 == 0 and c010 == 0 and c015 == 0:
            score += 3

        # Clustering positive for food, bars, and retail
        if group_name in ["Restaurant", "Bar", "Fashion & Retail",
                          "Home / Living Retail"]:
            if 2 <= c015 <= 8:
                score += 1

        scored.append({
            "group": group_name,
            "score": score,
            "c005": c005,
            "c010": c010,
            "c015": c015
        })

    scored = sorted(scored, key=lambda x: x["score"], reverse=True)

    primary = scored[0]
    secondary = scored[1]

    return primary, secondary

def build_opportunity_card(vlat, vlng):
    primary, secondary = get_primary_secondary_opportunities(vlat, vlng)

    primary_reason = (
        f"{primary['group']} has {primary['c005']} nearby within 0.05 mi, "
        f"{primary['c010']} within 0.10 mi, and {primary['c015']} within 0.15 mi."
    )

    secondary_reason = (
        f"{secondary['group']} has {secondary['c005']} nearby within 0.05 mi, "
        f"{secondary['c010']} within 0.10 mi, and {secondary['c015']} within 0.15 mi."
    )

    return f"""
    <div style='padding:14px 14px 12px 14px;background:#F8F6FF;border-bottom:1px solid #E8E3F5'>
      <div style='font-size:10px;font-weight:700;letter-spacing:1px;color:{PURPLE};margin-bottom:8px'>
        TENANT FIT SNAPSHOT
      </div>

      <div style='background:white;border:1px solid #E6E1F2;border-radius:8px;padding:10px 11px;margin-bottom:8px'>
        <div style='font-size:10px;color:#999;font-weight:700;letter-spacing:.7px;margin-bottom:3px'>PRIMARY OPPORTUNITY</div>
        <div style='font-size:15px;color:{NAVY};font-weight:700;line-height:1.25'>{primary["group"]}</div>
        <div style='font-size:11px;color:#666;line-height:1.45;margin-top:5px'>{primary_reason}</div>
      </div>

      <div style='background:white;border:1px solid #EFEAF8;border-radius:8px;padding:9px 11px'>
        <div style='font-size:10px;color:#999;font-weight:700;letter-spacing:.7px;margin-bottom:3px'>SECONDARY OPPORTUNITY</div>
        <div style='font-size:13px;color:{PURPLE};font-weight:700;line-height:1.25'>{secondary["group"]}</div>
        <div style='font-size:11px;color:#777;line-height:1.45;margin-top:5px'>{secondary_reason}</div>
      </div>
    </div>
    """

def build_gap_table(vlat, vlng, miles, label):
    nearby = biz[biz.apply(
        lambda r: haversine(vlat, vlng, r["lat"], r["lng"]) <= miles, axis=1
    )]
    total = len(nearby)
    type_counts = nearby.groupby("Business Type").size().to_dict()

    rows = ""
    for c in key_types:
        count = type_counts.get(c, 0)
        gap   = count == 0
        dot_color = VAC_RED if gap else GREEN
        flag_html = (
            f"<span style='background:{VAC_RED};color:white;border-radius:3px;"
            f"padding:1px 5px;font-size:10px;font-weight:600;letter-spacing:.3px'>GAP</span>"
            if gap else
            f"<span style='color:{GREEN};font-size:13px;font-weight:700'>✓</span>"
        )

        sub_html = ""
        if count > 0:
            subset     = nearby[nearby["Business Type"] == c]
            sub_counts = subset["Category"].dropna().value_counts()
            if len(sub_counts):
                subs = " · ".join([f"{k} <b>{v}</b>" for k, v in sub_counts.head(4).items()])
                sub_html = f"<div style='font-size:10px;color:#888;padding:1px 8px 5px 18px;line-height:1.5'>{subs}</div>"

        row_bg = "#FFF5F5" if gap else "transparent"
        rows += f"""
        <tr style='background:{row_bg}'>
          <td style='padding:4px 8px;color:#333;font-size:12px'>{c}</td>
          <td style='padding:4px 8px;text-align:center;font-size:12px;color:{NAVY};font-weight:600'>{count}</td>
          <td style='padding:4px 8px;text-align:center'>{flag_html}</td>
        </tr>
        <tr style='background:{row_bg}'><td colspan='3' style='padding:0'>{sub_html}</td></tr>"""

    return f"""
    <div style='margin-bottom:14px;border:1px solid #EBEBF0;border-radius:8px;overflow:hidden'>
      <div style='background:{NAVY};color:white;padding:7px 10px;display:flex;justify-content:space-between;align-items:center'>
        <span style='font-size:12px;font-weight:600;letter-spacing:.3px'>{label}</span>
        <span style='font-size:11px;opacity:.8'>{total} businesses</span>
      </div>
      <table style='width:100%;border-collapse:collapse'>
        <tr style='background:#F4F3FA'>
          <th style='text-align:left;padding:4px 8px;font-size:11px;color:#888;font-weight:500'>Type</th>
          <th style='padding:4px 8px;font-size:11px;color:#888;font-weight:500'>Count</th>
          <th style='padding:4px 8px;font-size:11px;color:#888;font-weight:500'>Access</th>
        </tr>
        {rows}
      </table>
    </div>"""


# Map
m = folium.Map(
    location=[37.7920, -122.4020],
    zoom_start=16,
    tiles=None
)

# OpenFreeMap Positron basemap
m.get_root().header.add_child(folium.Element("""
<link href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css" rel="stylesheet" />
<script src="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.js"></script>
<script src="https://unpkg.com/@maplibre/maplibre-gl-leaflet/leaflet-maplibre-gl.js"></script>
"""))

map_var = m.get_name()

m.get_root().html.add_child(folium.Element(f"""
<script>
document.addEventListener("DOMContentLoaded", function() {{
    L.maplibreGL({{
        style: "https://tiles.openfreemap.org/styles/positron"
    }}).addTo({map_var});
}});
</script>
"""))

# Fonts + FA
m.get_root().header.add_child(folium.Element("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"/>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  @font-face {
    font-family: 'Quasimoda';
    src: url('./Quasimoda-Medium.woff2') format('woff2');
    font-weight: 500;
    font-style: normal;
}
</style>
"""))

# JS: radius toggle, circles, dimming, restore
circle_js = f"""
<script>
var vacancyCircles = [];
var allMarkerLayers = [];

function clearCircles() {{
    vacancyCircles.forEach(function(c) {{ c.remove(); }});
    vacancyCircles = [];
}}

function haversineJS(lat1, lng1, lat2, lng2) {{
    var R = 3958.8;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLng = (lng2 - lng1) * Math.PI / 180;
    var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI/180) * Math.cos(lat2 * Math.PI/180) *
            Math.sin(dLng/2) * Math.sin(dLng/2);
    return R * 2 * Math.asin(Math.sqrt(a));
}}

function dimMarkers(focusLat, focusLng, radiusMiles) {{
    allMarkerLayers.forEach(function(obj) {{
        var dist = haversineJS(focusLat, focusLng, obj.lat, obj.lng);
        var el = obj.marker.getElement();
        if (el) {{
            el.style.transition = "opacity 0.3s";
            el.style.opacity = dist > radiusMiles ? "0.12" : "1.0";
        }}
    }});
}}

function restoreMarkers() {{
    allMarkerLayers.forEach(function(obj) {{
        var el = obj.marker.getElement();
        if (el) {{
            el.style.transition = "opacity 0.3s";
            el.style.opacity = "1.0";
        }}
    }});
}}

function showSingleRadius(map, lat, lng, radiusKey) {{
    clearCircles();

    var radiusInfo = {{
        "005": {{meters: 80,  miles: 0.05, color: "{GREEN}",  label: "0.05 mi"}},
        "010": {{meters: 160, miles: 0.10, color: "{PURPLE}", label: "0.10 mi"}},
        "015": {{meters: 241, miles: 0.15, color: "{NAVY}",   label: "0.15 mi"}}
    }};

    var r = radiusInfo[radiusKey] || radiusInfo["005"];

    var circle = L.circle([lat, lng], {{
        radius: r.meters,
        color: r.color,
        fill: true,
        fillColor: r.color,
        fillOpacity: 0.045,
        weight: 2.8,
        dashArray: "8 5",
        opacity: 0.9
    }}).addTo(map);

    vacancyCircles.push(circle);
    dimMarkers(lat, lng, r.miles);
}}

function selectRadius(button, lat, lng, radiusKey) {{
    var wrapper = button.closest(".radius-toggle-wrapper");

    if (wrapper) {{
        wrapper.querySelectorAll(".radius-panel").forEach(function(panel) {{
            panel.style.display = panel.dataset.radius === radiusKey ? "block" : "none";
        }});

        wrapper.querySelectorAll(".radius-toggle-btn").forEach(function(btn) {{
            btn.classList.remove("active-radius-btn");
        }});

        button.classList.add("active-radius-btn");
    }}

    if (window._map) {{
        showSingleRadius(window._map, lat, lng, radiusKey);
    }}
}}
</script>

<style>
  .leaflet-popup-content-wrapper {{
    border-radius: 12px !important;
    box-shadow: 0 8px 32px rgba(0,32,92,0.18) !important;
    padding: 0 !important;
    overflow: hidden;
    font-family: 'Inter', 'Quasimoda', sans-serif !important;
  }}
  .leaflet-popup-content {{
    margin: 0 !important;
    font-family: 'Inter', 'Quasimoda', sans-serif !important;
  }}
  .leaflet-popup-tip-container {{
    margin-top: -1px;
  }}
  .leaflet-popup-tip {{
    background: white !important;
  }}
  .leaflet-popup-close-button {{
    color: #999 !important;
    font-size: 18px !important;
    top: 10px !important;
    right: 12px !important;
  }}
  .leaflet-popup-close-button:hover {{
    color: {NAVY} !important;
  }}
  .leaflet-tooltip {{
    font-family: 'Inter', 'Quasimoda', sans-serif !important;
    font-size: 12px !important;
    border-radius: 6px !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(0,32,92,0.15) !important;
    padding: 5px 10px !important;
  }}

  .radius-toggle-btn {{
    border:1px solid #E5E1F0;
    background:white;
    color:#666;
    border-radius:14px;
    padding:4px 9px;
    font-size:11px;
    font-weight:700;
    cursor:pointer;
    font-family:'Inter','Quasimoda',sans-serif;
  }}

  .radius-toggle-btn:hover {{
    border-color:{PURPLE};
    color:{PURPLE};
  }}

  .active-radius-btn {{
    background:{NAVY} !important;
    border-color:{NAVY} !important;
    color:white !important;
  }}
</style>
"""

m.get_root().html.add_child(folium.Element(circle_js))

# Marker icon builder
def fa_icon(fa_class, bg_color, size=20):
    return folium.DivIcon(
        html=f"""
        <div style="background:{bg_color}; width:{size}px; height:{size}px;
                    border-radius:50%; border:2px solid rgba(255,255,255,0.9);
                    box-shadow: 0 2px 6px rgba(0,32,92,0.25);
                    display:flex; align-items:center; justify-content:center;
                    transition: transform 0.15s ease;">
          <i class="fas {fa_class}" style="color:white; font-size:{int(size*0.52)}px;"></i>
        </div>""",
        icon_size=(size, size),
        icon_anchor=(size//2, size//2),
        popup_anchor=(0, -(size//2))
    )

# Business markers
for _, row in biz.iterrows():
    style = get_style(row)

    btype = str(row.get('Business Type', '-'))
    cat   = str(row.get('Category', '-'))
    name  = str(row.get('Name', '?'))

    popup_html = f"""
    <div style='font-family:Inter,Quasimoda,sans-serif;width:260px'>
      <div style='background:{NAVY};color:white;padding:12px 14px 10px 14px'>
        <div style='font-size:14px;font-weight:700;line-height:1.3;margin-bottom:3px'>{name}</div>
        <div style='font-size:11px;opacity:0.7'>{row.get('FULL ADDRESS', '-')}</div>
      </div>
      <div style='padding:12px 14px;background:white'>
        <div style='display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px'>
          <span style='background:#F4F3FA;color:{PURPLE};font-size:11px;font-weight:600;
                       padding:2px 8px;border-radius:10px'>{btype}</span>
          {"" if cat == "-" or cat == "nan" else f'<span style="background:#F0FAF5;color:{GREEN};font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;border:1px solid {MINT}">{cat}</span>'}
        </div>
        <div style='font-size:12px;color:#555;line-height:1.8'>
          {"" if str(row.get("Cuisine Type","-")) in ["-","nan","None"] else f'<div><span style="color:#999;font-size:11px">CUISINE</span><br><b>{row.get("Cuisine Type")}</b></div>'}
          <div style='margin-top:4px'>
            <span style='display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;
              background:{"#E8F5E9" if str(row.get("Status","")).lower() in ["open","active"] else "#FFF3E0"};
              color:{"#2E7D32" if str(row.get("Status","")).lower() in ["open","active"] else "#E65100"}'>
              {row.get("Status", "-")}
            </span>
          </div>
        </div>
      </div>
    </div>"""

    folium.Marker(
        location=[row["lat"], row["lng"]],
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f'<b style="color:{NAVY}">{name}</b> &nbsp;<span style="color:#888;font-size:11px">{btype}</span>',
        icon=fa_icon(style["icon"], style["color"])
    ).add_to(m)


# Vacancy markers
for _, row in vac.iterrows():
    vlat, vlng = row["lat"], row["lng"]

    gap_005 = build_gap_table(vlat, vlng, 0.05, "Within 0.05 mi")
    gap_010 = build_gap_table(vlat, vlng, 0.10, "Within 0.10 mi")
    gap_015 = build_gap_table(vlat, vlng, 0.15, "Within 0.15 mi")

    opportunity_card = build_opportunity_card(vlat, vlng)

    sqft    = row.get('Sq ft', '-')
    vtype   = row.get('Type', '-')
    leasing = row.get('Leasing Firm', '-')
    contact = row.get('Contact', '-')
    address = row.get('Address', '-')

    popup_html = f"""
    <div style='font-family:Inter,Quasimoda,sans-serif;width:360px;max-height:560px;overflow-y:auto'
         onmouseenter="
           if(window._map) {{ showSingleRadius(window._map, {vlat}, {vlng}, '005'); }}
         ">

      <!-- Header -->
      <div style='background:linear-gradient(135deg,{VAC_RED} 0%,#C62828 100%);
                  color:white;padding:14px 16px 12px 16px;position:relative'>
        <div style='font-size:10px;font-weight:700;letter-spacing:1.5px;opacity:.75;margin-bottom:4px'>VACANT UNIT</div>
        <div style='font-size:15px;font-weight:700;line-height:1.3'>{address}</div>
        <div style='display:flex;gap:8px;margin-top:8px;flex-wrap:wrap'>
          {"" if str(sqft) in ["-","nan","None"] else f'<span style="background:rgba(255,255,255,0.2);font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600">{sqft} sq ft</span>'}
          {"" if str(vtype) in ["-","nan","None"] else f'<span style="background:rgba(255,255,255,0.2);font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600">{vtype}</span>'}
        </div>
      </div>

      <!-- Leasing info -->
      {"" if str(leasing) in ["-","nan","None"] else f'''
      <div style="padding:10px 14px;background:#FFF8F8;border-bottom:1px solid #FFE5E5;font-size:12px;color:#555">
        <span style="color:#999;font-size:10px;font-weight:600;letter-spacing:.5px">LEASING</span><br>
        <b style="color:{NAVY}">{leasing}</b>
        {"" if str(contact) in ["-","nan","None"] else f" &nbsp;·&nbsp; {contact}"}
      </div>
      '''}

      {opportunity_card}

      <!-- Nearby business mix with radius toggle -->
      <div class='radius-toggle-wrapper' style='padding:14px 14px 10px 14px;background:white'>
        <div style='font-size:11px;font-weight:700;letter-spacing:.8px;color:{PURPLE};margin-bottom:10px;
                    display:flex;align-items:center;gap:6px'>
          <span style='display:inline-block;width:18px;height:2px;background:{PURPLE}'></span>
          NEARBY BUSINESS MIX
          <span style='display:inline-block;width:18px;height:2px;background:{PURPLE}'></span>
        </div>

        <div style='display:flex;gap:6px;margin-bottom:10px'>
          <button class='radius-toggle-btn active-radius-btn'
                  onclick="selectRadius(this, {vlat}, {vlng}, '005')">
            0.05 mi
          </button>

          <button class='radius-toggle-btn'
                  onclick="selectRadius(this, {vlat}, {vlng}, '010')">
            0.10 mi
          </button>

          <button class='radius-toggle-btn'
                  onclick="selectRadius(this, {vlat}, {vlng}, '015')">
            0.15 mi
          </button>
        </div>

        <div class='radius-panel' data-radius='005' style='display:block'>
          {gap_005}
        </div>

        <div class='radius-panel' data-radius='010' style='display:none'>
          {gap_010}
        </div>

        <div class='radius-panel' data-radius='015' style='display:none'>
          {gap_015}
        </div>
      </div>
    </div>"""

    # Vacancy pin
    vac_icon = folium.DivIcon(
        html=f"""
        <div style="width:30px;height:30px;position:relative;display:flex;align-items:center;justify-content:center">
          <!-- Main pin -->
          <div style="width:24px;height:24px;background:linear-gradient(135deg,{VAC_RED},{CORAL});
                      border-radius:50% 50% 50% 0;transform:rotate(-45deg);
                      border:2.5px solid white;
                      box-shadow:0 3px 10px rgba(229,57,53,0.45)">
          </div>

          <!-- Icon inside pin -->
          <div style="position:absolute;width:18px;height:18px;
                      display:flex;align-items:center;justify-content:center;
                      transform:translate(-2px, -2px)">
            <i class="fas fa-building" style="color:white;font-size:8px"></i>
          </div>
        </div>""",
        icon_size=(30, 30),
        icon_anchor=(12, 24),
        popup_anchor=(0, -26)
    )

    folium.Marker(
        location=[vlat, vlng],
        popup=folium.Popup(popup_html, max_width=380),
        tooltip=f'<span style="color:{VAC_RED};font-weight:700">⬟ VACANT</span> &nbsp;<span style="color:#333">{address}</span> <span style="color:#888;font-size:11px">- click for tenant fit</span>',
        icon=vac_icon
    ).add_to(m)


# Wire up map variable
map_var = m.get_name()
m.get_root().html.add_child(folium.Element(f"""
<script>
  document.addEventListener("DOMContentLoaded", function() {{
    window._map = {map_var};

    {map_var}.eachLayer(function(layer) {{
      if (layer instanceof L.Marker) {{
        var ll = layer.getLatLng();
        allMarkerLayers.push({{ marker: layer, lat: ll.lat, lng: ll.lng }});
      }}
    }});

    {map_var}.on('popupclose', function() {{
      clearCircles();
      restoreMarkers();
    }});
  }});
</script>
"""))


# Legend
legend_html = f"""
<div style="position:fixed;bottom:32px;left:32px;z-index:1000;
     background:white;border-radius:12px;
     box-shadow:0 8px 32px rgba(0,32,92,0.18);
     font-family:'Inter','Quasimoda',sans-serif;
     overflow:hidden;min-width:190px">

  <!-- Header bar -->
  <div style="background:{NAVY};color:white;padding:10px 14px 8px 14px">
    <div style="font-size:11px;font-weight:700;letter-spacing:1px;opacity:.7">DOWNTOWN SF GROUND FLOOR MAP</div>
    <div style="font-size:13px;font-weight:700">Ground Floor Gap Identification</div>
  </div>

  <div style="padding:12px 14px">

    <!-- Business types -->
    <div style="font-size:10px;font-weight:700;letter-spacing:.8px;color:#AAA;margin-bottom:7px">BUSINESS TYPE</div>

    {"".join([f'''
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
      <div style="width:20px;height:20px;border-radius:50%;background:{style["color"]};
                  display:flex;align-items:center;justify-content:center;flex-shrink:0;
                  box-shadow:0 1px 4px rgba(0,0,0,.2)">
        <i class="fas {style["icon"]}" style="color:white;font-size:9px"></i>
      </div>
      <span style="font-size:12px;color:#333">{btype}</span>
    </div>''' for btype, style in type_styles.items()])}

    <div style="height:1px;background:#F0EEF8;margin:10px 0"></div>

    <!-- Vacancy -->
    <div style="font-size:10px;font-weight:700;letter-spacing:.8px;color:#AAA;margin-bottom:7px">VACANCY</div>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
      <div style="width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,{VAC_RED},{CORAL});
                  display:flex;align-items:center;justify-content:center;flex-shrink:0;
                  box-shadow:0 1px 4px rgba(229,57,53,.4)">
        <i class="fas fa-building" style="color:white;font-size:9px"></i>
      </div>
      <span style="font-size:12px;color:#333">Vacant Unit</span>
    </div>
    <div style="font-size:10px;color:#AAA;padding-left:28px;margin-bottom:8px">Click for tenant fit</div>

    <div style="height:1px;background:#F0EEF8;margin:10px 0"></div>

    <!-- Radii -->
    <div style="font-size:10px;font-weight:700;letter-spacing:.8px;color:#AAA;margin-bottom:7px">RADIUS RINGS</div>
    <div style="display:flex;flex-direction:column;gap:4px">
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:20px;height:2.5px;background:{GREEN};border-radius:2px"></div>
        <span style="font-size:11px;color:#555">0.05 mi (~80 m)</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:20px;height:2.5px;background:{PURPLE};border-radius:2px"></div>
        <span style="font-size:11px;color:#555">0.10 mi (~161 m)</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:20px;height:2.5px;background:{NAVY};border-radius:2px"></div>
        <span style="font-size:11px;color:#555">0.15 mi (~241 m)</span>
      </div>
    </div>

    <!-- Gap key -->
    <div style="height:1px;background:#F0EEF8;margin:10px 0"></div>
    <div style="display:flex;gap:10px">
      <div style="display:flex;align-items:center;gap:5px;font-size:11px;color:#555">
        <span style="background:{VAC_RED};color:white;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:600">GAP</span>
        Missing type
      </div>
      <div style="display:flex;align-items:center;gap:5px;font-size:11px;color:#555">
        <span style="color:{GREEN};font-size:14px;font-weight:700">✓</span>
        Present
      </div>
    </div>
  </div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

m.save("index.html")
print("Done")
