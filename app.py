import streamlit as st
import json
from pathlib import Path

# Page config
st.set_page_config(
    page_title="Charlotte Golf Guide",
    page_icon="⛳",
    layout="wide",
)

# Load course data
@st.cache_data
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

# --- Display Course Cards ---
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
