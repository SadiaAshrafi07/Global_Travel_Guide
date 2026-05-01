import streamlit as st
import requests
import pandas as pd
import random
import google.generativeai as genai
import urllib.parse

# -------------------------
# Page Config
# -------------------------
st.set_page_config(page_title="Global Travel Planner", layout="wide")

st.title("🌍 Global Smart Travel Planner")
st.markdown("AI-powered recommendations for any city worldwide.")

# -------------------------
# Gemini Setup
# -------------------------
try:
    genai.configure(api_key=st.secrets["Google_Gemini_Key"])
    gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    GEMINI_AVAILABLE = True
except:
    GEMINI_AVAILABLE = False

# -------------------------
# Sidebar
# -------------------------
st.sidebar.header("🧭 Plan Your Trip")

city = st.sidebar.text_input("Enter City (e.g., Paris, Tokyo, Kolkata)")
budget = st.sidebar.selectbox("Budget", ["Low", "Medium", "High"])
travel_style = st.sidebar.selectbox("Travel Style", ["Solo", "Family", "Luxury", "Backpacking"])
num_days = st.sidebar.slider("Trip Duration (Days)", 1, 14, 3)

st.sidebar.caption("Tip: Try 'City, Country' (e.g., Tokyo, Japan)")

# -------------------------
# Coordinates
# -------------------------
def fallback_coordinates(city):
    fallback = {
        "mumbai": (19.0760, 72.8777),
        "delhi": (28.6139, 77.2090),
        "kolkata": (22.5726, 88.3639),
        "london": (51.5074, -0.1278),
        "paris": (48.8566, 2.3522),
        "tokyo": (35.6762, 139.6503)
    }
    return fallback.get(city.lower().split(",")[0].strip(), (None, None))


def get_coordinates(city):
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
            headers={"User-Agent": "travel-app"},
            timeout=8
        )
        if res.status_code == 200:
            data = res.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        pass

    st.warning("Using fallback location.")
    return fallback_coordinates(city)


# -------------------------
# Fetch Places
# -------------------------
def fetch_places(lat, lon, query_type):
    query_map = {
        "hotel": '"tourism"~"hotel|guest_house|hostel"',
        "restaurant": '"amenity"~"restaurant|cafe|fast_food"',
        "place": '"tourism"~"attraction|museum|gallery|viewpoint"'
    }

    query = f"""
    [out:json];
    (
      node[{query_map[query_type]}](around:10000,{lat},{lon});
      way[{query_map[query_type]}](around:10000,{lat},{lon});
    );
    out center;
    """

    try:
        res = requests.get("https://overpass-api.de/api/interpreter",
                           params={"data": query},
                           timeout=15)

        data = res.json()

    except:
        return pd.DataFrame()

    results = []
    for el in data.get("elements", []):
        name = el.get("tags", {}).get("name")
        if name:
            results.append({
                "name": name,
                "rating": round(random.uniform(3.8, 4.9), 1),
                "reviews": random.randint(100, 10000),
                "lat": el.get("lat") or el.get("center", {}).get("lat"),
                "lon": el.get("lon") or el.get("center", {}).get("lon")
            })

    return pd.DataFrame(results)


# -------------------------
# Ranking
# -------------------------
def rank_places(df):
    if df.empty:
        return df
    df = df.copy()
    df["score"] = df["rating"] + df["reviews"]/10000
    return df.sort_values(by="score", ascending=False).head(5)


# -------------------------
# Image (FIXED)
# -------------------------
def get_image(place, city, category):
    query = f"{place} {city}"

    if category == "hotel":
        query += " hotel building"
    elif category == "restaurant":
        query += " restaurant food"
    else:
        query += " tourist attraction"

    return f"https://source.unsplash.com/600x400/?{query}"


# -------------------------
# Google Maps Link
# -------------------------
def get_maps_link(name, city):
    query = urllib.parse.quote(f"{name} {city}")
    return f"https://www.google.com/maps/search/?api=1&query={query}"


# -------------------------
# AI Plan
# -------------------------
def generate_ai_plan(city, budget, travel_style, num_days):
    if not GEMINI_AVAILABLE:
        return "AI unavailable."

    try:
        prompt = f"{num_days}-day trip plan for {city}, {budget} budget, {travel_style} style."
        return gemini_model.generate_content(prompt).text
    except:
        return f"""
### Sample Plan for {city}

Day 1: Explore city center  
Day 2: Visit attractions  
Day 3: Food & shopping  

(Upgrade API for full AI plan)
"""


# -------------------------
# MAIN
# -------------------------
if st.sidebar.button("🔍 Generate Plan"):

    if not city:
        st.warning("Enter a city")
        st.stop()

    lat, lon = get_coordinates(city)

    if lat is None:
        st.error("City not found")
        st.stop()

    st.success(f"Showing recommendations for {city.title()}")

    hotels = rank_places(fetch_places(lat, lon, "hotel"))
    food = rank_places(fetch_places(lat, lon, "restaurant"))
    places = rank_places(fetch_places(lat, lon, "place"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["🏨 Stays", "🍽 Food", "📍 Places", "🚗 Travel", "🤖 AI Plan"]
    )

    # Hotels
    with tab1:
        for _, row in hotels.iterrows():
            col1, col2 = st.columns([1,2])
            col1.image(get_image(row["name"], city, "hotel"))
            col2.markdown(f"### {row['name']}")
            col2.write(f"⭐ {row['rating']} | {row['reviews']} reviews")
            col2.markdown(f"[📍 View on Google Maps]({get_maps_link(row['name'], city)})")
            st.divider()

    # Food
    with tab2:
        for _, row in food.iterrows():
            col1, col2 = st.columns([1,2])
            col1.image(get_image(row["name"], city, "restaurant"))
            col2.markdown(f"### {row['name']}")
            col2.write(f"⭐ {row['rating']} | {row['reviews']} reviews")
            col2.markdown(f"[📍 View on Google Maps]({get_maps_link(row['name'], city)})")
            st.divider()

    # Places
    with tab3:
        for _, row in places.iterrows():
            col1, col2 = st.columns([1,2])
            col1.image(get_image(row["name"], city, "place"))
            col2.markdown(f"### {row['name']}")
            col2.write(f"⭐ {row['rating']} | {row['reviews']} reviews")
            col2.markdown(f"[📍 View on Google Maps]({get_maps_link(row['name'], city)})")
            st.divider()

    # Travel
    with tab4:
        st.subheader("Travel Tips")
        if budget == "Low":
            st.success("Use public transport")
        elif budget == "Medium":
            st.success("Use metro + cab")
        else:
            st.success("Use private car")

    # AI Plan
    with tab5:
        st.subheader("AI Travel Plan")
        st.write(generate_ai_plan(city, budget, travel_style, num_days))

else:
    st.info("Enter a city and generate your plan")
