import streamlit as st
import requests
import pandas as pd
import random
import google.generativeai as genai
import pydeck as pdk

# -------------------------
# Page Config
# -------------------------
st.set_page_config(page_title="Global Travel Planner", layout="wide")

st.title("🌍 Global Smart Travel Planner")
st.markdown("AI-powered recommendations for any city worldwide.")

# -------------------------
# FIX 1: Gemini setup moved inside a try/except to prevent crash
# on missing secret key (e.g. local dev without secrets.toml)
# -------------------------
try:
    genai.configure(api_key=st.secrets["Google_Gemini_Key"])
    gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

# -------------------------
# Sidebar Inputs
# -------------------------
st.sidebar.header("🧭 Plan Your Trip")

city = st.sidebar.text_input("Enter City (e.g., Paris, Tokyo, Kolkata)")
budget = st.sidebar.selectbox("Budget", ["Low", "Medium", "High"])
travel_style = st.sidebar.selectbox("Travel Style", ["Solo", "Family", "Luxury", "Backpacking"])
num_days = st.sidebar.slider("Trip Duration (Days)", 1, 14, 3)  # ADDITION: trip duration

st.sidebar.caption("Tip: Try 'City, Country' (e.g., Tokyo, Japan)")

# -------------------------
# Fallback Coordinates
# ADDITION: expanded fallback city list
# -------------------------
def fallback_coordinates(city):
    fallback_cities = {
        "tokyo": (35.6762, 139.6503),
        "delhi": (28.6139, 77.2090),
        "mumbai": (19.0760, 72.8777),
        "kolkata": (22.5726, 88.3639),
        "paris": (48.8566, 2.3522),
        "london": (51.5074, -0.1278),
        "new york": (40.7128, -74.0060),
        "dubai": (25.2048, 55.2708),
        "singapore": (1.3521, 103.8198),
        "sydney": (-33.8688, 151.2093),
        "bangkok": (13.7563, 100.5018),
        "rome": (41.9028, 12.4964),
        "barcelona": (41.3851, 2.1734),
        "amsterdam": (52.3676, 4.9041),
        "istanbul": (41.0082, 28.9784),
    }
    key = city.lower().split(",")[0].strip()
    return fallback_cities.get(key, (None, None))


# -------------------------
# Get Coordinates
# FIX 2: Added specific exception logging; avoid bare except swallowing errors silently
# -------------------------
def get_coordinates(city):
    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "global-travel-app (sadiauzma23@gmail.com)",
        "Accept-Language": "en"
    }
    params = {"q": city, "format": "json", "limit": 1}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except requests.exceptions.Timeout:
        st.warning("⏱️ Location lookup timed out. Using fallback data.")
    except requests.exceptions.ConnectionError:
        st.warning("🔌 Network error. Using fallback data.")
    except Exception as e:
        st.warning(f"⚠️ Unexpected error: {e}. Using fallback data.")

    coords = fallback_coordinates(city)
    if coords != (None, None):
        st.info("📌 Using built-in coordinates for this city.")
    return coords


# -------------------------
# Fetch Places
# FIX 3: Overpass radius reduced from 50000m to 10000m — 50km is too wide
#         and causes huge slow responses / timeouts for most cities.
# FIX 4: timeout raised to 20s; Overpass can be slow under load.
# FIX 5: Added `name:en` fallback for non-English city names.
# -------------------------
def fetch_places(lat, lon, query_type):
    query_map = {
        "hotel":      '"tourism"~"hotel|guest_house|hostel"',
        "restaurant": '"amenity"~"restaurant|cafe|fast_food"',
        "place":      '"tourism"~"attraction|museum|gallery|viewpoint"'
    }

    query = f"""
    [out:json][timeout:25];
    (
      node[{query_map[query_type]}](around:10000,{lat},{lon});
      way[{query_map[query_type]}](around:10000,{lat},{lon});
    );
    out center;
    """

    try:
        res = requests.get(
            "https://overpass-api.de/api/interpreter",
            params={"data": query},
            timeout=20,
            headers={"User-Agent": "global-travel-app"}
        )
        if res.status_code != 200:
            return pd.DataFrame()
        data = res.json()
    except requests.exceptions.Timeout:
        st.warning(f"⏱️ Timed out fetching {query_type} data.")
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    results = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        # FIX 5: prefer English name if available
        name = tags.get("name:en") or tags.get("name")
        if name:
            results.append({
                "name":      name,
                "rating":    round(random.uniform(3.8, 4.9), 1),
                "reviews":   random.randint(100, 10000),
                "sentiment": round(random.uniform(0.7, 0.95), 2),
                "lat":       el.get("lat") or el.get("center", {}).get("lat"),
                "lon":       el.get("lon") or el.get("center", {}).get("lon"),
                # ADDITION: extract website/phone if available
                "website":   tags.get("website", ""),
                "phone":     tags.get("phone", ""),
            })

    return pd.DataFrame(results)


# -------------------------
# Ranking
# FIX 6: Guard against empty DataFrame more explicitly (len check)
# -------------------------
def rank_places(df):
    if df is None or len(df) == 0:
        return pd.DataFrame()
    df = df.copy()
    df["score"] = (
        df["rating"]   * 0.4 +
        df["sentiment"] * 0.3 +
        (df["reviews"] / 10000) * 0.3
    )
    return df.sort_values(by="score", ascending=False).head(5).reset_index(drop=True)


# -------------------------
# Images
# NOTE: source.unsplash.com was fully shut down — returns broken "0" text.
# Using Wikimedia Commons REST API as primary (real relevant photos),
# with a deterministic Lorem Picsum fallback (always works, random travel photo).
# -------------------------
def get_image_url(place, city):
    """
    Try Wikimedia Commons for a real photo of the place.
    Falls back to Lorem Picsum (stable, always returns a photo).
    Returns a working image URL string.
    """
    try:
        search_term = f"{place} {city}"
        wiki_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + search_term.replace(" ", "_")
        res = requests.get(wiki_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            thumb = data.get("thumbnail", {}).get("source", "")
            if thumb:
                return thumb
    except Exception:
        pass

    # Fallback: Lorem Picsum — deterministic seed from place name so same place = same image
    seed = abs(hash(place)) % 1000
    return f"https://picsum.photos/seed/{seed}/600/400"


# -------------------------
# Map
# FIX 8: Map was only showing "places" — now accepts any df.
# ADDITION: Tooltip showing place name on hover.
# -------------------------
def show_map(lat, lon, df):
    if df is None or len(df) == 0:
        st.info("No map data available.")
        return

    df = df.dropna(subset=["lat", "lon"]).copy()

    if len(df) == 0:
        st.info("No coordinates available for map.")
        return

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[lon, lat]",
        get_radius=150,
        get_fill_color="[255, 80, 0, 180]",
        pickable=True,
    )

    view = pdk.ViewState(latitude=lat, longitude=lon, zoom=13, pitch=40)

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip={"text": "{name}"},   # FIX 8: hover tooltip
        map_style="mapbox://styles/mapbox/light-v9"
    ))


# -------------------------
# AI Plan
# FIX 9: model variable renamed to gemini_model to avoid shadowing Python built-ins.
#        Added num_days to the prompt for more specific output.
#        Added explicit check for GEMINI_AVAILABLE.
# -------------------------
def generate_ai_plan(city, budget, travel_style, num_days):
    if not GEMINI_AVAILABLE:
        return "⚠️ Gemini API key not configured. Add `Google_Gemini_Key` to your `.streamlit/secrets.toml`."
    try:
        prompt = (
            f"Create a detailed {num_days}-day {travel_style} travel itinerary for {city} "
            f"with a {budget} budget. For each day include: morning, afternoon, evening activities, "
            f"recommended local food, estimated costs, and practical tips."
        )
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI service unavailable: {e}"


# -------------------------
# ADDITION: Currency / budget estimator helper
# -------------------------
BUDGET_RANGES = {
    "Low":    {"hotel": "$20–50/night",  "food": "$5–15/meal",  "transport": "$1–5/day"},
    "Medium": {"hotel": "$60–120/night", "food": "$15–35/meal", "transport": "$10–20/day"},
    "High":   {"hotel": "$150+/night",   "food": "$40+/meal",   "transport": "$30+/day"},
}

TRANSPORT_TIPS = {
    "Low":    "🚌 Use local buses, metro, and shared taxis. Walk where possible.",
    "Medium": "🚕 Mix metro with ride-share apps (Uber/Ola/Grab). Occasional cab.",
    "High":   "🚗 Private transfers, airport pickup, and chauffeured day trips.",
}


# -------------------------
# MAIN
# -------------------------
if st.sidebar.button("🔍 Generate Plan"):

    if not city.strip():
        st.warning("⚠️ Please enter a city name.")
        st.stop()

    if "," not in city:
        st.info("💡 Tip: Adding country improves accuracy — e.g. 'Kochi, India'")

    with st.spinner("📍 Finding location..."):
        lat, lon = get_coordinates(city)

    if lat is None:
        st.error("❌ Could not find this city. Try a more specific name or check spelling.")
        st.stop()

    st.success(f"✅ Showing recommendations for **{city.title()}**")

    with st.spinner("🔍 Fetching places data... (may take 10–20 seconds)"):
        hotels = rank_places(fetch_places(lat, lon, "hotel"))
        food   = rank_places(fetch_places(lat, lon, "restaurant"))
        places = rank_places(fetch_places(lat, lon, "place"))

    if hotels.empty and food.empty and places.empty:
        st.warning("😕 No results found for this city. Try a larger nearby city.")
        st.stop()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["🏨 Stays", "🍽️ Food", "📍 Places", "🗺️ Map", "🚗 Travel & Budget", "🤖 AI Plan"]
    )

    # ── Tab 1: Hotels ──────────────────────────────────────────────────────────
    with tab1:
        st.subheader("🏨 Recommended Stays")
        if hotels.empty:
            st.info("No hotels found nearby.")
        else:
            for i, row in hotels.iterrows():
                with st.container():
                    col_img, col_info = st.columns([1, 2])
                    with col_img:
                        st.image(get_image_url(row["name"], city), use_column_width=True)
                    with col_info:
                        st.markdown(f"### {row['name']}")
                        st.write(f"⭐ **{row['rating']}** &nbsp; | &nbsp; 💬 {row['reviews']:,} reviews")
                        if row.get("website"):
                            st.markdown(f"🌐 [Website]({row['website']})")
                        if row.get("phone"):
                            st.write(f"📞 {row['phone']}")
                st.divider()

    # ── Tab 2: Food ────────────────────────────────────────────────────────────
    with tab2:
        st.subheader("🍽️ Recommended Restaurants & Cafes")
        if food.empty:
            st.info("No restaurants found nearby.")
        else:
            for i, row in food.iterrows():
                with st.container():
                    col_img, col_info = st.columns([1, 2])
                    with col_img:
                        st.image(get_image_url(row["name"], city), use_column_width=True)
                    with col_info:
                        st.markdown(f"### {row['name']}")
                        st.write(f"⭐ **{row['rating']}** &nbsp; | &nbsp; 💬 {row['reviews']:,} reviews")
                        if row.get("website"):
                            st.markdown(f"🌐 [Website]({row['website']})")
                        if row.get("phone"):
                            st.write(f"📞 {row['phone']}")
                st.divider()

    # ── Tab 3: Places ──────────────────────────────────────────────────────────
    with tab3:
        st.subheader("📍 Top Attractions")
        if places.empty:
            st.info("No attractions found nearby.")
        else:
            for i, row in places.iterrows():
                with st.container():
                    col_img, col_info = st.columns([1, 2])
                    with col_img:
                        st.image(get_image_url(row["name"], city), use_column_width=True)
                    with col_info:
                        st.markdown(f"### {row['name']}")
                        st.write(f"⭐ **{row['rating']}** &nbsp; | &nbsp; 💬 {row['reviews']:,} reviews")
                        if row.get("website"):
                            st.markdown(f"🌐 [Website]({row['website']})")
                st.divider()

    # ── Tab 4: Map ─────────────────────────────────────────────────────────────
    with tab4:
        st.subheader("🗺️ Map View")
        map_choice = st.radio("Show on map:", ["Places", "Hotels", "Restaurants"], horizontal=True)
        map_df = {"Places": places, "Hotels": hotels, "Restaurants": food}[map_choice]
        show_map(lat, lon, map_df)

    # ── Tab 5: Travel & Budget ─────────────────────────────────────────────────
    with tab5:
        st.subheader("🚗 Transport & 💰 Budget Guide")

        st.markdown(f"#### Transport Tip")
        st.success(TRANSPORT_TIPS[budget])

        st.markdown(f"#### Estimated Daily Costs — **{budget} Budget**")
        b = BUDGET_RANGES[budget]
        col1, col2, col3 = st.columns(3)
        col1.metric("🏨 Hotel / Night", b["hotel"])
        col2.metric("🍽️ Meal Cost",     b["food"])
        col3.metric("🚌 Transport/Day", b["transport"])

        # ADDITION: simple total trip estimator
        st.markdown("#### 🧮 Estimated Trip Cost")
        nights = num_days
        low_hotel  = int(b["hotel"].split("$")[1].split("–")[0].replace("+",""))
        high_hotel = int(b["hotel"].split("–")[-1].replace("/night","").replace("+","")) if "–" in b["hotel"] else low_hotel + 100
        low_food   = int(b["food"].split("$")[1].split("–")[0].replace("+","")) * 3
        high_food  = int(b["food"].split("–")[-1].replace("/meal","").replace("+","")) * 3 if "–" in b["food"] else low_food + 30

        low_est  = (low_hotel + low_food) * nights
        high_est = (high_hotel + high_food) * nights
        st.info(f"For a **{num_days}-day** trip: **~${low_est}–${high_est}** (excluding flights & activities)")

    # ── Tab 6: AI Plan ─────────────────────────────────────────────────────────
    with tab6:
        st.subheader("🤖 AI-Generated Travel Itinerary")
        with st.spinner("✍️ Generating your personalised itinerary..."):
            ai_text = generate_ai_plan(city, budget, travel_style, num_days)
        st.markdown(ai_text)

else:
    st.info("👈 Enter a city in the sidebar and click **Generate Plan** to get started.")
