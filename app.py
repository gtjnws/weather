import os
from datetime import date, timedelta
import requests
import streamlit as st
from branca.colormap import LinearColormap
import folium
from streamlit.components.v1 import html as st_html

RAPIDAPI_KEY = "d8045b5110mshe046a58d22872d9p1e0733jsnca715ec19725"
GEODB_URL = "https://wft-geo-db.p.rapidapi.com/v1/geo/countries/{}/places"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

EURO_TOURISM_TOP15 = [
    ("Frankrijk", "FR"), ("Spanje", "ES"), ("Italië", "IT"), ("Turkije", "TR"),
    ("Duitsland", "DE"), ("Verenigd Koninkrijk", "GB"), ("Oostenrijk", "AT"),
    ("Griekenland", "GR"), ("Nederland", "NL"), ("Portugal", "PT"), ("Polen", "PL"),
    ("Tsjechië", "CZ"), ("Zwitserland", "CH"), ("Hongarije", "HU"), ("Kroatië", "HR"),
]

def get_largest_cities(country_code: str, limit: int):
    headers = {"X-RapidAPI-Host": "wft-geo-db.p.rapidapi.com","X-RapidAPI-Key": RAPIDAPI_KEY}
    params = {"types": "CITY", "sort": "-population", "limit": limit}
    r = requests.get(GEODB_URL.format(country_code), headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json().get("data", [])
    return [{"name": d["name"], "lat": d["latitude"], "lon": d["longitude"]} for d in data]

def fetch_city_forecast(lat, lon, target_date):
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto", "start_date": target_date, "end_date": target_date,
    }
    r = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    r.raise_for_status()
    d = r.json().get("daily", {})
    if d.get("temperature_2m_max") and d.get("temperature_2m_min"):
        return {"tmax": float(d["temperature_2m_max"][0]), "tmin": float(d["temperature_2m_min"][0])}
    return None

def build_map(results, target_date):
    tmax_values = [r["tmax"] for r in results if r.get("tmax") is not None]
    if not tmax_values:
        raise RuntimeError("Geen temperatuurgegevens beschikbaar.")
    vmin, vmax = min(tmax_values), max(tmax_values)
    spread = max(4.0, (vmax - vmin) or 6.0)
    vmin -= spread * 0.15
    vmax += spread * 0.15

    colormap = LinearColormap(["#2c7bb6","#abd9e9","#ffffbf","#fdae61","#d7191c"], vmin=vmin, vmax=vmax)
    colormap.caption = f"Max. temperatuur (°C) op {target_date}"

    mlat = sum(r["lat"] for r in results) / len(results)
    mlon = sum(r["lon"] for r in results) / len(results)
    m = folium.Map(location=[mlat, mlon], zoom_start=5, tiles="CartoDB positron")

    for r in results:
        if r.get("tmax") is None:
            popup_html, color = f"<b>{r['name']}</b><br>Geen gegevens.", "#808080"
        else:
            popup_html = (f"<b>{r['name']}</b><br>Datum: {target_date}<br>"
                          f"Max: {r['tmax']:.1f}°C<br>Min: {r['tmin']:.1f}°C")
            color = colormap(r["tmax"])
        folium.CircleMarker(location=[r["lat"], r["lon"]], radius=9, color=color,
                            fill=True, fill_opacity=0.9, weight=2, popup=popup_html).add_to(m)
    colormap.add_to(m)
    return m

st.set_page_config(page_title="Weerkaart Europa", layout="centered")
st.title("🌦️ Weerkaart – grootste steden per land")

land_naam = st.selectbox("Land", [n for n, _ in EURO_TOURISM_TOP15], index=0)
land_code = dict(EURO_TOURISM_TOP15)[land_naam]
aantal_steden = st.number_input("Aantal steden", 1, 50, 10, 1)
dagen_vooruit = st.number_input("Dagen vooruit", 1, 14, 7, 1)

if st.button("Genereer kaart"):
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "PLAATS_HIER_JE_RAPIDAPI_KEY":
        st.error("Vul eerst je RAPIDAPI_KEY in de code in.")
    else:
        target_date = (date.today() + timedelta(days=int(dagen_vooruit))).isoformat()
        try:
            with st.spinner("Steden ophalen…"):
                cities = get_largest_cities(land_code, int(aantal_steden))
            results = []
            for i, c in enumerate(cities, start=1):
                st.write(f"Weer ophalen voor **{c['name']}** ({i}/{len(cities)})…")
                fc = fetch_city_forecast(c["lat"], c["lon"], target_date)
                results.append({**c, **(fc or {"tmax": None, "tmin": None})})

            m = build_map(results, target_date)
            html_str = m._repr_html_()
            st_html(html_str, height=600)
        except Exception as e:
            st.error(f"Er ging iets mis: {e}")
