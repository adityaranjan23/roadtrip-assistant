import streamlit as st
import requests

st.set_page_config(page_title="RoadTrip Assistant", page_icon="🚗", layout="centered")
st.title("🚗 RoadTrip Assistant")
st.markdown("""
Welcome to the interactive RoadTrip Assistant! 🌍

Try:
- `Show me the route from Delhi to Manali`
- `What's the distance from Mumbai to Pune?`
- `Find attractions between Jaipur and Agra`
- `Nearest gas station from Bangalore to Mysore`
- `Find attractions in Shimla`
""")

# --- Helper Functions ---
def geocode_location(location):
    url = f"https://nominatim.openstreetmap.org/search?q={location}, India&format=json&limit=1"
    headers = {"User-Agent": "RoadTripAssistant/1.0"}
    try:
        response = requests.get(url, headers=headers).json()
        if response:
            return float(response[0]["lat"]), float(response[0]["lon"])
        return None, None
    except:
        return None, None

def get_route(origin, destination):
    orig_lat, orig_lon = geocode_location(origin)
    dest_lat, dest_lon = geocode_location(destination)
    if not orig_lat or not dest_lat:
        return None, "Could not geocode one or both locations."
    url = f"http://router.project-osrm.org/route/v1/driving/{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=false"
    try:
        response = requests.get(url).json()
        if response["code"] == "Ok":
            route = response["routes"][0]
            return {
                "distance": route["distance"] / 1000,
                "duration": route["duration"] / 3600
            }, None
        else:
            return None, f"OSRM error: {response['code']}"
    except Exception as e:
        return None, str(e)

def find_attractions_in_city(city):
    lat, lon = geocode_location(city)
    if not lat:
        return [], f"Could not geocode city: {city}"

    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
        node["tourism"="attraction"](around:20000,{lat},{lon});
        node["historic"](around:20000,{lat},{lon});
        node["natural"](around:20000,{lat},{lon});
        node["leisure"](around:20000,{lat},{lon});
        node["amenity"="place_of_worship"](around:20000,{lat},{lon});
    );
    out 15;
    """
    try:
        res = requests.post(overpass_url, data={"data": query})
        data = res.json()
        results = []
        for elem in data.get("elements", []):
            name = elem.get("tags", {}).get("name", "Unnamed")
            type_ = elem.get("tags", {}).get("tourism") or elem.get("tags", {}).get("historic") or \
                    elem.get("tags", {}).get("natural") or elem.get("tags", {}).get("leisure") or \
                    elem.get("tags", {}).get("amenity", "Unknown")
            results.append((name, type_, elem.get("lat"), elem.get("lon")))
        return results, None
    except Exception as e:
        return [], str(e)

# --- Main UI ---
user_input = st.text_input("Enter your road trip query:", "")
if user_input:
    with st.spinner("Processing..."):
        if "find attractions in" in user_input.lower():
            city = user_input.lower().split("find attractions in")[-1].strip()
            attractions, err = find_attractions_in_city(city)
            if err:
                st.error(err)
            elif attractions:
                st.subheader(f"🗺️ Attractions in {city.title()}")
                for name, type_, lat, lon in attractions[:10]:
                    st.write(f"• **{name}** ({type_}) – `{lat:.4f}, {lon:.4f}`")
            else:
                st.warning(f"No attractions found in {city.title()}.")

        elif "from" in user_input.lower() and "to" in user_input.lower():
            if "between" in user_input.lower():
                parts = user_input.lower().split("between")[-1].split("and")
            else:
                parts = user_input.lower().split("from")[-1].split("to")
            origin = parts[0].strip()
            destination = parts[1].strip()
            route, err = get_route(origin, destination)
            if err:
                st.error(err)
            elif route:
                if "distance" in user_input.lower():
                    st.success(f"Distance from {origin} to {destination}: {route['distance']:.1f} km (~{route['duration']:.1f} hrs)")
                else:
                    st.success(f"Route from {origin} to {destination} found!")
                    st.write(f"- Distance: {route['distance']:.1f} km")
                    st.write(f"- Duration: {route['duration']:.1f} hours")
        else:
            st.info("Try a supported format like: `Find attractions in Jaipur` or `Show me the route from Delhi to Agra`")
