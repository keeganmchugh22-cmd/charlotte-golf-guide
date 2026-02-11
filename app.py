import streamlit as st
import json
from pathlib import Path
import folium
from streamlit_folium import st_folium
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Charlotte Golf Guide",
    page_icon="⛳",
    layout="wide",
)

# Load course data
@st.cache_data(ttl=60)  # Cache for 60 seconds, then reload
def load_courses():
    data_path = Path(__file__).parent / "charlotte_courses.json"
    with open(data_path, "r") as f:
        return json.load(f)

courses = load_courses()

# --- Header ---
st.title("⛳ Charlotte Golf Guide")
st.caption("Your guide to public golf in the Queen City")
st.divider()

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
    st.info("🚧 Photo Gallery coming soon! We'll use Google Places API to fetch real course photos.")
    st.markdown("**Note:** This feature requires the Places API to be enabled on your Google Cloud project.")
