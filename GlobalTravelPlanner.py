import streamlit as st
import requests
import pandas as pd
import random
import google.generativeai as genai

st.set_page_config(page_title="Global Travel Planner", layout="wide")

st.title("🌍 Global Smart Travel Planner")
st.markdown("AI-powered recommendations for any city worldwide.")

# -------------------------
# Configure Gemini API
# -------------------------
genai.configure(api_key=st.secrets["Google_Gemini_Key"])
model = genai.GenerativeModel("gemini-pro")

# -------------------------
# Sidebar Inputs
# -------------------------
st.sidebar.header("🧭 Plan Your Trip")

city = st.sidebar.text_input("Enter City (e.g., Paris, Tokyo, Kolkata)")
budget = st.sidebar.selectbox("Budget", ["Low", "Medium", "High"])
travel_style = st.sidebar.selectbox("Travel Style", ["Solo", "Family", "Luxury", "Backpacking"])

# -------------------------
# Get Coordinates (OpenStreetMap)
# -------------------------
def get_coordinates(city):
    url = f"https://nominatim.openstreetmap.org/search?city={city}&format=json"
    response = requests.get(url).json()
    if response:
        return float(response[0]["lat"]), float(response[0]["lon"])
    return None, None

# -------------------------
# Fetch Places (Overpass API)
# -------------------------
def fetch_places(lat, lon, query_type):
    query_map = {
        "hotel": "tourism=hotel",
        "restaurant": "amenity=restaurant",
        "place": "tourism=attraction"
    }

    query = f"""
    [out:json];
    node[{query_map[query_type]}](around:3000,{lat},{lon});
    out;
    """

    response = requests.get("http://overpass-api.de/api/interpreter", params={'data': query})
    data = response.json()

    results = []
    for el in data.get("elements", []):
        name = el.get("tags", {}).get("name")
        if name:
            results.append({
                "name": name,
                "rating": round(random.uniform(3.8, 4.9), 1),
                "reviews": random.randint(100, 10000),
                "sentiment": round(random.uniform(0.7, 0.95), 2)
            })

    return pd.DataFrame(results)

# -------------------------
# Ranking Logic
# -------------------------
def rank_places(df):
    if df.empty:
        return df
    df["score"] = (df["rating"] * 0.5) + (df["sentiment"] * 0.3) + (df["reviews"]/10000 * 0.2)
    return df.sort_values(by="score", ascending=False).head(3)

# -------------------------
# Gemini AI Insights
# -------------------------
def generate_ai_insights(city, budget, travel_style):
    prompt = f"""
    Suggest a travel plan for {city}.
    Budget: {budget}
    Travel style: {travel_style}

    Include:
    - Best areas to stay
    - Top cuisines to try
    - Travel tips
    - 1-day itinerary
    """

    response = model.generate_content(prompt)
    return response.text

# -------------------------
# Image Prompt Generator (Gemini)
# -------------------------
def generate_image_prompt(place, city):
    prompt = f"Create a vivid travel description image prompt for {place} in {city}"
    response = model.generate_content(prompt)
    return response.text

# -------------------------
# Travel Mode Logic
# -------------------------
def get_travel_mode(budget):
    if budget == "Low":
        return "Public transport (Metro/Bus)"
    elif budget == "Medium":
        return "Public + Taxi"
    else:
        return "Taxi / Rental Car"

# -------------------------
# Main Execution
# -------------------------
if st.sidebar.button("🔍 Generate Plan"):

    if not city:
        st.warning("Please enter a city.")
    else:
        lat, lon = get_coordinates(city)

        if lat is None:
            st.error("City not found.")
        else:
            st.success(f"Showing recommendations for {city.title()}")

            hotels = rank_places(fetch_places(lat, lon, "hotel"))
            food = rank_places(fetch_places(lat, lon, "restaurant"))
            places = rank_places(fetch_places(lat, lon, "place"))

            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["🏨 Stays", "🍽 Food", "📍 Places", "🚗 Travel", "🤖 AI Plan"]
            )

            # ---------------- Hotels ----------------
            with tab1:
                for _, row in hotels.iterrows():
                    st.subheader(row["name"])
                    st.write(f"⭐ {row['rating']} | Reviews: {row['reviews']}")
                    st.caption(generate_image_prompt(row["name"], city))

            # ---------------- Food ----------------
            with tab2:
                for _, row in food.iterrows():
                    st.subheader(row["name"])
                    st.write(f"⭐ {row['rating']} | Reviews: {row['reviews']}")
                    st.caption(generate_image_prompt(row["name"], city))

            # ---------------- Places ----------------
            with tab3:
                for _, row in places.iterrows():
                    st.subheader(row["name"])
                    st.write(f"⭐ {row['rating']} | Reviews: {row['reviews']}")
                    st.caption(generate_image_prompt(row["name"], city))

            # ---------------- Travel ----------------
            with tab4:
                st.subheader("Best Travel Mode")
                st.success(get_travel_mode(budget))
                st.info("Tip: Use Google Maps for live navigation.")

            # ---------------- AI Plan ----------------
            with tab5:
                st.subheader("AI Travel Plan")
                with st.spinner("Generating plan..."):
                    plan = generate_ai_insights(city, budget, travel_style)
                    st.write(plan)

else:
    st.info("👈 Enter a city and generate your plan")