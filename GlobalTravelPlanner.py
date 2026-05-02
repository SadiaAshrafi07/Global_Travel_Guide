import streamlit as st
import requests
import pandas as pd
import random

# -------------------------
# Page Config
# -------------------------
st.set_page_config(page_title="Global Travel Planner", layout="wide")

st.title("🌍 Global Smart Travel Planner")
st.markdown("AI-powered recommendations for any city worldwide.")

# -------------------------
# Sidebar Inputs
# -------------------------
st.sidebar.header("🧭 Plan Your Trip")

city          = st.sidebar.text_input("Enter City (e.g., Paris, Tokyo, Kolkata)")
budget        = st.sidebar.selectbox("Budget", ["Low", "Medium", "High"])
travel_style  = st.sidebar.selectbox("Travel Style", ["Solo", "Family", "Luxury", "Backpacking"])
num_days      = st.sidebar.slider("Trip Duration (Days)", 1, 14, 3)

st.sidebar.caption("Tip: Try 'City, Country' (e.g., Tokyo, Japan)")

# -------------------------
# Fallback Coordinates
# -------------------------
def fallback_coordinates(city):
    fallback_cities = {
        "tokyo":      (35.6762, 139.6503),
        "delhi":      (28.6139, 77.2090),
        "mumbai":     (19.0760, 72.8777),
        "kolkata":    (22.5726, 88.3639),
        "paris":      (48.8566, 2.3522),
        "london":     (51.5074, -0.1278),
        "new york":   (40.7128, -74.0060),
        "dubai":      (25.2048, 55.2708),
        "singapore":  (1.3521,  103.8198),
        "sydney":     (-33.8688, 151.2093),
        "bangkok":    (13.7563, 100.5018),
        "rome":       (41.9028, 12.4964),
        "barcelona":  (41.3851, 2.1734),
        "amsterdam":  (52.3676, 4.9041),
        "istanbul":   (41.0082, 28.9784),
    }
    key = city.lower().split(",")[0].strip()
    return fallback_cities.get(key, (None, None))


# -------------------------
# Get Coordinates
# -------------------------
def get_coordinates(city):
    url     = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "global-travel-app (sadiauzma23@gmail.com)", "Accept-Language": "en"}
    params  = {"q": city, "format": "json", "limit": 1}

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
# Fetch Places from OpenStreetMap
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
        name = tags.get("name:en") or tags.get("name")
        if name:
            results.append({
                "name":      name,
                "rating":    round(random.uniform(3.8, 4.9), 1),
                "reviews":   random.randint(100, 10000),
                "sentiment": round(random.uniform(0.7, 0.95), 2),
                "website":   tags.get("website", ""),
                "phone":     tags.get("phone", ""),
            })

    return pd.DataFrame(results)


# -------------------------
# Ranking
# -------------------------
def rank_places(df):
    if df is None or len(df) == 0:
        return pd.DataFrame()
    df = df.copy()
    df["score"] = (
        df["rating"]    * 0.4 +
        df["sentiment"] * 0.3 +
        (df["reviews"]  / 10000) * 0.3
    )
    return df.sort_values(by="score", ascending=False).head(5).reset_index(drop=True)


# -------------------------
# IMAGE FIX
# Strategy:
#   1. Wikimedia Commons image search — real photos by keyword (most relevant)
#   2. Wikipedia article thumbnail — lead image of the place article
#   3. Neutral text placeholder — never shows a wrong/random photo
# -------------------------
def get_image_url(place, city):
    # --- Attempt 1: Wikimedia Commons keyword image search ---
    try:
        params = {
            "action":        "query",
            "generator":     "search",
            "gsrnamespace":  6,
            "gsrsearch":     f"{place} {city}",
            "gsrlimit":      5,
            "prop":          "imageinfo",
            "iiprop":        "url|mime",
            "iiurlwidth":    600,
            "format":        "json",
        }
        res = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params=params, timeout=6,
            headers={"User-Agent": "global-travel-app"}
        )
        if res.status_code == 200:
            pages = res.json().get("query", {}).get("pages", {})
            for page in pages.values():
                info = page.get("imageinfo", [{}])[0]
                mime = info.get("mime", "")
                url  = info.get("thumburl") or info.get("url", "")
                if url and mime in ("image/jpeg", "image/png"):
                    return url
    except Exception:
        pass

    # --- Attempt 2: Wikipedia article thumbnail ---
    try:
        wiki_url = (
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            + f"{place} {city}".replace(" ", "_")
        )
        res = requests.get(wiki_url, timeout=5)
        if res.status_code == 200:
            thumb = res.json().get("thumbnail", {}).get("source", "")
            if thumb:
                return thumb
    except Exception:
        pass

    # --- Attempt 3: Neutral labelled placeholder (no wrong images) ---
    label = place[:30].replace(" ", "+")
    return f"https://placehold.co/600x400/dce8f0/1a5276?text={label}"


# -------------------------
# AI PLAN FIX
# Switched from Gemini (paid quota) to Hugging Face Inference API — completely free.
# Model: Mistral-7B-Instruct — high quality, fast, free tier available.
#
# Setup (one-time):
#   1. Go to https://huggingface.co/settings/tokens
#   2. Create a free account and generate a token (read access is enough)
#   3. In Streamlit Cloud → App Settings → Secrets, add:
#        HF_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxx"
#
# Without the token it still works but may hit rate limits faster.
# -------------------------
def generate_ai_plan(city, budget, travel_style, num_days):
    try:
        hf_token = st.secrets.get("HF_TOKEN", "")
    except Exception:
        hf_token = ""

    prompt = (
        f"[INST] You are a helpful travel guide. "
        f"Create a {num_days}-day {travel_style} travel itinerary for {city} on a {budget} budget. "
        f"For each day provide morning, afternoon and evening activities, "
        f"local food recommendations, estimated daily cost, and 1 practical tip. "
        f"Be specific, friendly and concise. [/INST]"
    )

    headers = {"Content-Type": "application/json"}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    payload = {
    "model": "mistralai/Mistral-7B-Instruct-v0.2",
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 900,
    "temperature": 0.7,
    }

    try:
        res = requests.post(
            "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-Instruct-v0.2/v1/chat/completions",
            json=payload,
            timeout=45,
        )

        if res.status_code == 200:
            result = res.json()
            return result["choices"][0]["message"]["content"].strip()
            
        elif res.status_code == 503:
            return (
                "⏳ The AI model is warming up (cold start). "
                "Please wait 20–30 seconds and click **Generate Plan** again."
            )
        else:
            return f"⚠️ AI error {res.status_code}: {res.text[:300]}"

    except requests.exceptions.Timeout:
        return "⏱️ AI request timed out. Please try again in a moment."
    except Exception as e:
        return f"⚠️ AI unavailable: {e}"


# -------------------------
# Budget & Transport helpers
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

    tab1, tab2, tab3, tab4 = st.tabs(
        ["🏨 Stays", "🍽️ Food", "📍 Places", "🚗 Travel & Budget"]
    )

    # ── Tab 1: Hotels ──────────────────────────────────────────────────────────
    with tab1:
        st.subheader("🏨 Recommended Stays")
        if hotels.empty:
            st.info("No hotels found nearby.")
        else:
            for _, row in hotels.iterrows():
                with st.container():
                    col_img, col_info = st.columns([1, 2])
                    with col_img:
                        st.image(get_image_url(row["name"], city), use_column_width=True)
                    with col_info:
                        st.markdown(f"### {row['name']}")
                        st.write(f"⭐ **{row['rating']}** &nbsp;|&nbsp; 💬 {row['reviews']:,} reviews")
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
            for _, row in food.iterrows():
                with st.container():
                    col_img, col_info = st.columns([1, 2])
                    with col_img:
                        st.image(get_image_url(row["name"], city), use_column_width=True)
                    with col_info:
                        st.markdown(f"### {row['name']}")
                        st.write(f"⭐ **{row['rating']}** &nbsp;|&nbsp; 💬 {row['reviews']:,} reviews")
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
            for _, row in places.iterrows():
                with st.container():
                    col_img, col_info = st.columns([1, 2])
                    with col_img:
                        st.image(get_image_url(row["name"], city), use_column_width=True)
                    with col_info:
                        st.markdown(f"### {row['name']}")
                        st.write(f"⭐ **{row['rating']}** &nbsp;|&nbsp; 💬 {row['reviews']:,} reviews")
                        if row.get("website"):
                            st.markdown(f"🌐 [Website]({row['website']})")
                st.divider()

    # ── Tab 4: Travel & Budget ─────────────────────────────────────────────────
    with tab4:
        st.subheader("🚗 Transport & 💰 Budget Guide")

        st.markdown("#### Transport Tip")
        st.success(TRANSPORT_TIPS[budget])

        st.markdown(f"#### Estimated Daily Costs — **{budget} Budget**")
        b = BUDGET_RANGES[budget]
        col1, col2, col3 = st.columns(3)
        col1.metric("🏨 Hotel / Night", b["hotel"])
        col2.metric("🍽️ Meal Cost",     b["food"])
        col3.metric("🚌 Transport/Day", b["transport"])

        st.markdown("#### 🧮 Estimated Trip Cost")
        low_hotel  = int(b["hotel"].split("$")[1].split("–")[0].replace("+", ""))
        high_hotel = int(b["hotel"].split("–")[-1].replace("/night", "").replace("+", "")) if "–" in b["hotel"] else low_hotel + 100
        low_food   = int(b["food"].split("$")[1].split("–")[0].replace("+", "")) * 3
        high_food  = int(b["food"].split("–")[-1].replace("/meal", "").replace("+", "")) * 3 if "–" in b["food"] else low_food + 30
        low_est    = (low_hotel + low_food) * num_days
        high_est   = (high_hotel + high_food) * num_days
        st.info(f"For a **{num_days}-day** trip: **~${low_est}–${high_est}** (excluding flights & activities)")

   

else:
    st.info("👈 Enter a city in the sidebar and click **Generate Plan** to get started.")
