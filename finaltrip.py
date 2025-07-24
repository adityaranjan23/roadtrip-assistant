import streamlit as st
import requests
import re
import polyline # Library to decode OSRM's polyline format


# --- Configuration ---
st.set_page_config(page_title="RoadTrip Assistant", page_icon="🚗", layout="centered")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_ROUTE_URL = "http://router.project-osrm.org/route/v1/driving"
OVERPASS_API_URL = "http://overpass-api.de/api/interpreter"

# IMPORTANT: Replace with your actual Google Maps API Key
GOOGLE_MAPS_API_KEY = "AIzaSyA4Domfyft7dHB8EMCeqZcRvMcU9fFdtVA"

# --- Helper Functions ---

def geocode_location(location: str):
    """
    Geocodes a given location string to latitude and longitude using Nominatim.
    Args:
        location (str): The name of the location (e.g., "Delhi").
    Returns:
        tuple: (latitude, longitude) or (None, None) if geocoding fails.
    """
    params = {
        "q": f"{location}, India",
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "RoadTripAssistant/1.0 (streamlit-app)"}

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
        st.warning(f"Could not find coordinates for '{location}'. Please check the spelling.")
        return None, None
    except requests.exceptions.Timeout:
        st.error(f"Geocoding request for '{location}' timed out. Please try again.")
        return None, None
    except requests.exceptions.RequestException as e:
        st.error(f"Error geocoding '{location}': {e}")
        return None, None
    except ValueError:
        st.error(f"Invalid coordinate data received for '{location}'.")
        return None, None

def get_route(origin: str, destination: str):
    """
    Calculates the driving route between two locations using OSRM.
    Now also returns the polyline for map display.
    Args:
        origin (str): Starting location.
        destination (str): Ending location.
    Returns:
        tuple: (route_info_dict, polyline_string, error_message)
               route_info_dict: {"distance": km, "duration": hours}
               polyline_string: Encoded polyline string from OSRM
               error_message: str or None
    """
    orig_lat, orig_lon = geocode_location(origin)
    dest_lat, dest_lon = geocode_location(destination)

    if not orig_lat or not dest_lat:
        return None, None, "Failed to geocode one or both locations."

    # Request overview=full to get the full polyline geometry
    url = f"{OSRM_ROUTE_URL}/{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=full&geometries=polyline"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data["code"] == "Ok":
            if data["routes"]:
                route = data["routes"][0]
                return {
                    "distance": route["distance"] / 1000,
                    "duration": route["duration"] / 3600
                }, route.get("geometry"), None # Return geometry
            else:
                return None, None, "No route found between these locations. Are they accessible by road?"
        else:
            return None, None, f"Routing service error: {data.get('code', 'Unknown error')}. Details: {data.get('message', 'N/A')}"
    except requests.exceptions.Timeout:
        return None, None, "Routing request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return None, None, f"Error fetching route: {e}"

def find_attractions_in_city(city: str, radius_km: int = 20):
    """
    Finds attractions in a given city using Overpass API.
    Args:
        city (str): The city to search for attractions.
        radius_km (int): Search radius in kilometers.
    Returns:
        tuple: (list_of_attractions, error_message)
               list_of_attractions: List of (name, type, lat, lon) tuples
               error_message: str or None
    """
    lat, lon = geocode_location(city)
    if not lat:
        return [], f"Could not geocode city: {city}"

    overpass_query = f"""
    [out:json];
    (
        node["tourism"~"attraction|museum|theme_park"](around:{radius_km * 1000},{lat},{lon});
        node["historic"~"castle|monument|ruins|memorial|fort"](around:{radius_km * 1000},{lat},{lon});
        node["natural"~"park|garden|peak|waterfall"](around:{radius_km * 1000},{lat},{lon});
        node["leisure"~"park|garden|zoo|stadium"](around:{radius_km * 1000},{lat},{lon});
        node["amenity"~"place_of_worship|theatre|library"](around:{radius_km * 1000},{lat},{lon});
    );
    out 15;
    """
    try:
        response = requests.post(OVERPASS_API_URL, data={"data": overpass_query}, timeout=20)
        response.raise_for_status()
        data = response.json()
        results = []
        for elem in data.get("elements", []):
            name = elem.get("tags", {}).get("name", "Unnamed Attraction")
            type_ = elem.get("tags", {}).get("tourism") or \
                    elem.get("tags", {}).get("historic") or \
                    elem.get("tags", {}).get("natural") or \
                    elem.get("tags", {}).get("leisure") or \
                    elem.get("tags", {}).get("amenity", "Unknown Type")
            results.append((name, type_, elem.get("lat"), elem.get("lon")))
        return results, None
    except requests.exceptions.Timeout:
        return [], f"Attraction search for '{city}' timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return [], f"Error fetching attractions for '{city}': {e}"

def display_google_map_with_route(route_polyline: str, origin_coords: tuple, destination_coords: tuple):
    """
    Embeds a Google Map with the given route polyline.
    Args:
        route_polyline (str): The encoded polyline string for the route.
        origin_coords (tuple): (lat, lon) of the origin.
        destination_coords (tuple): (lat, lon) of the destination.
    """
    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY == "AIzaSyA4Domfyft7dHB8EMCeqZcRvMcU9fFdtVA":
        st.error("Please set your Google Maps API Key in the `GOOGLE_MAPS_API_KEY` variable to display the map.")
        return

    # Decode the OSRM polyline to a list of lat/lon pairs for Google Maps
    # OSRM uses Google's encoded polyline algorithm
    decoded_path = polyline.decode(route_polyline)

    # Convert path to Google Maps LatLng literal format
    js_path_array = str([{"lat": lat, "lng": lon} for lat, lon in decoded_path])

    # Calculate center of the route for initial map view
    center_lat = (origin_coords[0] + destination_coords[0]) / 2
    center_lon = (origin_coords[1] + destination_coords[1]) / 2

    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Google Map Route</title>
        <style>
            html, body {{
                height: 100%;
                margin: 0;
                padding: 0;
            }}
            #map {{
                height: 500px; /* Fixed height for the map */
                width: 100%;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            function initMap() {{
                const map = new google.maps.Map(document.getElementById("map"), {{
                    zoom: 7, // Adjust zoom level as needed
                    center: {{ lat: {center_lat}, lng: {center_lon} }},
                    mapId: "DEMO_MAP_ID" // Use a map ID for custom styling if desired
                }});

                // Define the polyline path
                const routePath = new google.maps.Polyline({{
                    path: {js_path_array},
                    geodesic: true,
                    strokeColor: "#FF0000", // Red color for the route
                    strokeOpacity: 0.8,
                    strokeWeight: 5
                }});

                routePath.setMap(map);

                // Add markers for origin and destination
                new google.maps.Marker({{
                    position: {{ lat: {origin_coords[0]}, lng: {origin_coords[1]} }},
                    map: map,
                    title: "Origin"
                }});

                new google.maps.Marker({{
                    position: {{ lat: {destination_coords[0]}, lng: {destination_coords[1]} }},
                    map: map,
                    title: "Destination"
                }});

                // Fit map to the bounds of the polyline
                const bounds = new google.maps.LatLngBounds();
                for (let i = 0; i < routePath.getPath().getLength(); i++) {{
                    bounds.extend(routePath.getPath().getAt(i));
                }}
                map.fitBounds(bounds);
            }}
        </script>
        <script async defer src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_MAPS_API_KEY}&callback=initMap&libraries=geometry">
        </script>
    </body>
    </html>
    """
    st.components.v1.html(map_html, height=520) # Adjust height as needed

# --- Main Streamlit Application UI ---

st.title("🚗 RoadTrip Assistant")
st.markdown("""
Welcome to the interactive RoadTrip Assistant! 🌍

I can help you with:
- **Route Planning**: `Show me the route from Delhi to Manali`
- **Distance Calculation**: `What's the distance from Mumbai to Pune?`
- **Attraction Discovery**: `Find attractions in Shimla`


**Try these examples:**
- `Show me the route from Delhi to Manali`
- `What's the distance from Mumbai to Pune?`
- `Find attractions in Jaipur`
""")

user_input = st.text_input("Enter your road trip query:", "")

if user_input:
    with st.spinner("Processing your request..."):
        user_input_lower = user_input.lower()

        attraction_match = re.search(r"find attractions in (.+)", user_input_lower)
        route_distance_match = re.search(r"(?:show me the route|what's the distance) from (.+) to (.+)", user_input_lower)

        if attraction_match:
            city = attraction_match.group(1).strip()
            st.info(f"Searching for attractions in {city.title()}...")
            attractions, err = find_attractions_in_city(city)
            if err:
                st.error(err)
            elif attractions:
                st.subheader(f"🗺️ Top Attractions in {city.title()}")
                for name, type_, lat, lon in attractions:
                    st.write(f"• **{name}** ({type_}) – Lat: `{lat:.4f}`, Lon: `{lon:.4f}`")
            else:
                st.warning(f"No significant attractions found near {city.title()} within the search radius.")

        elif route_distance_match:
            origin = route_distance_match.group(1).strip()
            destination = route_distance_match.group(2).strip()
            st.info(f"Calculating route from {origin.title()} to {destination.title()}...")

            # Geocode origin and destination separately to get coordinates for map centering
            orig_lat, orig_lon = geocode_location(origin)
            dest_lat, dest_lon = geocode_location(destination)

            if not orig_lat or not dest_lat:
                st.error("Could not geocode one or both locations for route display.")
            else:
                route, polyline_str, err = get_route(origin, destination)
                if err:
                    st.error(err)
                elif route:
                    st.success(f"Route details from {origin.title()} to {destination.title()}:")
                    st.write(f"- **Distance**: {route['distance']:.1f} km")
                    st.write(f"- **Estimated Duration**: {route['duration']:.1f} hours")

                    if polyline_str:
                        st.subheader("📍 Route on Map:")
                        display_google_map_with_route(polyline_str, (orig_lat, orig_lon), (dest_lat, dest_lon))
                    else:
                        st.warning("Could not get polyline data to display the route on the map.")
                else:
                    st.error("Could not determine route details. Please try different locations or a more specific query.")

        else:
            st.info("I couldn't understand your request. Please try one of the examples provided above.")
