import streamlit as st
import json
from pathlib import Path
import folium
from streamlit_folium import st_folium
import requests
import os
from dotenv import load_dotenv
import random
import time

# Load environment variables
load_dotenv()

# Google Maps API Key
GOOGLE_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

# Page config
st.set_page_config(
    page_title="Charlotte Golf Guide",
    page_icon="⛳",
    layout="wide",
)

# --- Google Places API Functions ---
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in miles"""
    from math import radians, sin, cos, sqrt, atan2

    R = 3959  # Earth's radius in miles
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_place_id(course_name, address, latitude=None, longitude=None):
    """Search for a place and return its place_id with location verification"""
    try:
        # Use Text Search API for better control
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

        # Build query with "golf course" to be more specific
        query = f"{course_name} golf course {address}"

        params = {
            'query': query,
            'key': GOOGLE_API_KEY
        }

        # Add location bias if coordinates provided
        if latitude and longitude:
            params['location'] = f"{latitude},{longitude}"
            params['radius'] = 5000  # 5km radius

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data['status'] == 'OK' and data.get('results'):
            # Get the first result
            place = data['results'][0]
            place_id = place['place_id']

            # Verify location if coordinates provided
            if latitude and longitude:
                place_lat = place['geometry']['location']['lat']
                place_lng = place['geometry']['location']['lng']
                distance = calculate_distance(latitude, longitude, place_lat, place_lng)

                # If place is more than 2 miles away, it's probably wrong
                if distance > 2.0:
                    print(f"[DEV] Warning: {course_name} found {distance:.2f} miles away - might be incorrect. PlaceID: {place_id}")
                    return None

            print(f"[DEV] Found placeId for {course_name}: {place_id}")
            return place_id
        print(f"[DEV] No results found for {course_name}")
        return None
    except Exception as e:
        print(f"[DEV] Error searching for {course_name}: {str(e)}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_place_photos(place_id, max_photos=5):
    """Get photo references for a place"""
    try:
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            'place_id': place_id,
            'fields': 'photos',
            'key': GOOGLE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if data['status'] == 'OK' and 'result' in data:
            photos = data['result'].get('photos', [])
            print(f"[DEV] Fetched {len(photos)} photos for placeId {place_id}")
            return photos[:max_photos]
        print(f"[DEV] No photos returned for placeId {place_id} (status: {data.get('status')})")
        return []
    except Exception as e:
        print(f"[DEV] Error fetching photos for {place_id}: {str(e)}")
        return []

def get_photo_url(photo_reference, max_width=400):
    """Generate photo URL from photo reference"""
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={max_width}&photo_reference={photo_reference}&key={GOOGLE_API_KEY}"

# Load course data
@st.cache_data(ttl=60)  # Cache for 60 seconds, then reload
def load_courses():
    data_path = Path(__file__).parent / "charlotte_courses.json"
    with open(data_path, "r") as f:
        return json.load(f)

courses = load_courses()

# --- Verification Function (dev only) ---
@st.cache_data(ttl=3600)
def verify_all_courses_photos():
    """Verify which courses have valid placeIds and photos (dev debugging)"""
    results = []
    for course in courses:
        place_id = get_place_id(
            course['name'],
            course['address'],
            course.get('latitude'),
            course.get('longitude')
        )
        photos = get_place_photos(place_id, max_photos=1) if place_id else []
        results.append({
            'name': course['name'],
            'has_place_id': place_id is not None,
            'place_id': place_id,
            'photo_count': len(photos)
        })
        time.sleep(0.1)  # Rate limit
    return results

# --- Header ---
st.title("⛳ Charlotte Golf Guide")
st.caption("Your guide to public golf in the Queen City")
st.divider()

# --- Dev Sidebar (hidden by default) ---
with st.sidebar.expander("🔧 Dev Tools"):
    if st.button("Verify all courses (photos coverage)"):
        st.info("Running verification... check terminal for [DEV] logs")
        results = verify_all_courses_photos()

        courses_with_photos = sum(1 for r in results if r['photo_count'] > 0)
        courses_with_place_id = sum(1 for r in results if r['has_place_id'])

        st.write(f"**Summary:** {courses_with_place_id}/{len(results)} courses found in Google Places")
        st.write(f"**Photos available:** {courses_with_photos}/{len(results)} courses have photos")

        st.divider()
        st.write("**Details:**")
        for r in results:
            status = "✅" if r['photo_count'] > 0 else "❌"
            st.write(f"{status} {r['name']}: placeId={'✓' if r['has_place_id'] else '✗'}, photos={r['photo_count']}")

# --- Sidebar Filters ---
st.sidebar.header("Filter Courses")

search = st.sidebar.text_input("Search by course name")

prices = [c["weekday_price"] for c in courses]
min_price, max_price = min(prices), max(prices)
price_range = st.sidebar.slider(
    "Weekday Price Range",
    min_value=min_price,
    max_value=max_price,
    value=(min_price, max_price),
    format="$%d",
)

min_stars = st.sidebar.slider(
    "Minimum Star Rating",
    min_value=1.0,
    max_value=5.0,
    value=1.0,
    step=0.5,
)

hole_filter = st.sidebar.radio(
    "Number of Holes",
    options=["All", "9-Hole Only", "18-Hole Only"],
    horizontal=True,
)

# --- Sort Options ---
sort_option = st.sidebar.selectbox(
    "Sort By",
    options=[
        "Name (A-Z)",
        "Price: Low to High",
        "Price: High to Low",
        "Rating: High to Low",
        "Yardage: Long to Short",
    ],
)

# --- Apply Filters ---
filtered = courses

if search:
    filtered = [c for c in filtered if search.lower() in c["name"].lower()]

filtered = [c for c in filtered if price_range[0] <= c["weekday_price"] <= price_range[1]]
filtered = [c for c in filtered if c["star_rating"] >= min_stars]

if hole_filter == "9-Hole Only":
    filtered = [c for c in filtered if c["holes"] == 9]
elif hole_filter == "18-Hole Only":
    filtered = [c for c in filtered if c["holes"] == 18]

# --- Apply Sort ---
if sort_option == "Name (A-Z)":
    filtered.sort(key=lambda c: c["name"])
elif sort_option == "Price: Low to High":
    filtered.sort(key=lambda c: c["weekday_price"])
elif sort_option == "Price: High to Low":
    filtered.sort(key=lambda c: c["weekday_price"], reverse=True)
elif sort_option == "Rating: High to Low":
    filtered.sort(key=lambda c: c["star_rating"], reverse=True)
elif sort_option == "Yardage: Long to Short":
    filtered.sort(key=lambda c: c["yardage"], reverse=True)

# --- Results Count ---
st.markdown(f"**Showing {len(filtered)} of {len(courses)} courses**")

# --- Create Tabs ---
tab1, tab2, tab3 = st.tabs(["📋 Course List", "🗺️ Map View", "📸 Photo Gallery"])

# --- TAB 1: Course List ---
with tab1:
    if not filtered:
        st.info("No courses match your current filters. Try adjusting the sidebar options.")
    else:
        for course in filtered:
            with st.container(border=True):
                col_left, col_right = st.columns([2, 1])

                with col_left:
                    st.subheader(course["name"])
                    stars = "⭐" * int(course["star_rating"])
                    if course["star_rating"] % 1 >= 0.5:
                        stars += "½"
                    st.markdown(f"{stars} ({course['star_rating']}/5)")
                    st.markdown(f"*{course['description']}*")

                with col_right:
                    st.metric("Weekday", f"${course['weekday_price']}")
                    st.metric("Weekend", f"${course['weekend_price']}")

                st.divider()

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f"**Address:** {course['address']}")
                    st.markdown(f"**Phone:** {course['phone']}")
                with c2:
                    st.markdown(f"**Holes:** {course['holes']}  |  **Par:** {course['par']}")
                    st.markdown(f"**Yardage:** {course['yardage']:,}")
                with c3:
                    st.markdown(f"**Slope:** {course['slope']}")
                    st.markdown(f"**Course Rating:** {course['rating']}")
                with c4:
                    st.markdown(f"**Designer:** {course['designer']}")
                    st.markdown(f"**Year Opened:** {course['year_opened']}")

                range_status = "✅ Yes" if course["driving_range"] else "❌ No"
                st.markdown(f"**Driving Range:** {range_status}  |  **Type:** {course['course_type']}")

# --- TAB 2: Map View ---
with tab2:
    if not filtered:
        st.info("No courses match your current filters.")
    else:
        # Filter courses that have coordinates
        courses_with_coords = [c for c in filtered if 'latitude' in c and 'longitude' in c]

        if not courses_with_coords:
            st.error("No courses have location data available. Please check the data file.")
        else:
            # Calculate center of map
            avg_lat = sum(c['latitude'] for c in courses_with_coords) / len(courses_with_coords)
            avg_lng = sum(c['longitude'] for c in courses_with_coords) / len(courses_with_coords)

            # Create map
            m = folium.Map(location=[avg_lat, avg_lng], zoom_start=10)

            # Add markers for each course
            for course in courses_with_coords:
                # Create popup content
                popup_html = f"""
                <div style="width: 250px;">
                    <h4>{course['name']}</h4>
                    <p><b>Rating:</b> {'⭐' * int(course['star_rating'])} ({course['star_rating']}/5)</p>
                    <p><b>Weekday:</b> ${course['weekday_price']} | <b>Weekend:</b> ${course['weekend_price']}</p>
                    <p><b>Holes:</b> {course['holes']} | <b>Par:</b> {course['par']}</p>
                    <p><b>Phone:</b> {course['phone']}</p>
                    <p style="margin-top: 10px;">
                        <a href="https://www.google.com/maps/dir/?api=1&destination={course['latitude']},{course['longitude']}"
                           target="_blank" style="color: #1f77b4; text-decoration: none;">
                           📍 Get Directions
                        </a>
                    </p>
                </div>
                """

                # Marker color based on rating
                if course['star_rating'] >= 4.0:
                    color = 'green'
                elif course['star_rating'] >= 3.0:
                    color = 'blue'
                else:
                    color = 'orange'

                folium.Marker(
                    location=[course['latitude'], course['longitude']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=course['name'],
                    icon=folium.Icon(color=color, icon='golf-ball-tee', prefix='fa')
                ).add_to(m)

            # Display map
            st_folium(m, width=1400, height=600)

            # Legend
            st.markdown("**Legend:** 🟢 4+ stars | 🔵 3-4 stars | 🟠 <3 stars")

# --- TAB 3: Photo Gallery ---
with tab3:
    if not GOOGLE_API_KEY:
        st.error("Google Maps API key not found. Please add it to your .env file.")
    else:
        st.markdown("### 📸 Golf Course Photo Gallery")

        # Initialize session state for stable random selection
        if 'random_courses_showcase' not in st.session_state:
            st.session_state.random_courses_showcase = random.sample(filtered, min(5, len(filtered)))

        # Track selected course to reset photos on change
        if 'last_selected_course' not in st.session_state:
            st.session_state.last_selected_course = None

        # Course selector dropdown
        course_names = [c['name'] for c in filtered]
        selected_option = st.selectbox(
            "Select a course to view photos:",
            options=[None] + course_names,
            format_func=lambda x: "Select a course..." if x is None else x,
            help="Choose a course to view its photos"
        )

        st.divider()

        # STATE A: No course selected → show 5 random photos
        if selected_option is None:
            st.markdown("#### 🌟 Featured Course Photos")
            st.caption("Explore photos from different courses - select one above to see more")

            # Use stable random selection from session state
            random_courses = st.session_state.random_courses_showcase

            with st.spinner("Loading photos from Google Places..."):
                photo_data = []
                for course in random_courses:
                    place_id = get_place_id(
                        course['name'],
                        course['address'],
                        course.get('latitude'),
                        course.get('longitude')
                    )
                    if place_id:
                        photos = get_place_photos(place_id, max_photos=1)
                        if photos:
                            photo_data.append({
                                'course': course,
                                'photo_ref': photos[0]['photo_reference']
                            })
                        time.sleep(0.1)  # Rate limiting

                if photo_data:
                    # Display in grid
                    cols = st.columns(min(3, len(photo_data)))
                    for idx, item in enumerate(photo_data):
                        with cols[idx % 3]:
                            photo_url = get_photo_url(item['photo_ref'], max_width=400)
                            st.image(photo_url, use_container_width=True)
                            st.markdown(f"**{item['course']['name']}**")
                            stars = "⭐" * int(item['course']['star_rating'])
                            st.caption(f"{stars} ({item['course']['star_rating']}/5)")
                            st.markdown("---")
                else:
                    st.info("📸 Photos coming soon! Check back later.")

        # STATE B & C: Course selected
        else:
            selected_course = next(c for c in filtered if c['name'] == selected_option)

            # Log course selection for debugging
            print(f"[DEV] Gallery: User selected course '{selected_course['name']}'")

            st.markdown(f"#### {selected_course['name']}")
            col_info1, col_info2 = st.columns([2, 1])
            with col_info1:
                stars = "⭐" * int(selected_course['star_rating'])
                if selected_course['star_rating'] % 1 >= 0.5:
                    stars += "½"
                st.markdown(f"{stars} ({selected_course['star_rating']}/5)")
                st.caption(selected_course['address'])
            with col_info2:
                st.metric("Weekday", f"${selected_course['weekday_price']}")

            st.divider()

            # STATE B: Loading
            with st.spinner(f"Looking for photos…"):
                place_id = get_place_id(
                    selected_course['name'],
                    selected_course['address'],
                    selected_course.get('latitude'),
                    selected_course.get('longitude')
                )

                # STATE C: Course selected + empty/error
                if not place_id:
                    print(f"[DEV] Failed to find placeId for {selected_course['name']}")
                    st.info("📸 Photos coming soon!")
                else:
                    photos = get_place_photos(place_id, max_photos=5)
                    print(f"[DEV] {selected_course['name']} — placeId: {place_id}, photos returned: {len(photos)}")

                    if not photos:
                        st.info("📸 Photos coming soon!")
                    else:
                        # Display photos in grid (no "We found X photos" message)
                        cols = st.columns(3)
                        for idx, photo in enumerate(photos):
                            with cols[idx % 3]:
                                photo_url = get_photo_url(photo['photo_reference'], max_width=400)
                                st.image(photo_url, use_container_width=True)

                        # Course details below photos
                        st.divider()
                        st.markdown("**Course Details**")
                        detail_cols = st.columns(4)
                        with detail_cols[0]:
                            st.metric("Holes", selected_course['holes'])
                            st.metric("Par", selected_course['par'])
                        with detail_cols[1]:
                            st.metric("Yardage", f"{selected_course['yardage']:,}")
                            st.metric("Slope", selected_course['slope'])
                        with detail_cols[2]:
                            st.metric("Rating", selected_course['rating'])
                            st.metric("Type", selected_course['course_type'])
                        with detail_cols[3]:
                            st.metric("Designer", selected_course['designer'])
                            st.metric("Opened", selected_course['year_opened'])
