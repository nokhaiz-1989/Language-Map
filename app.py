import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import requests
import json
import os


# -------------------------------
# PAGE CONFIGURATION
# -------------------------------

st.set_page_config(
    page_title="Pakistan Cultural & Linguistic Atlas",
    page_icon="🌐",
    layout="wide"
)


# -------------------------------
# CUSTOM STYLING
# -------------------------------

st.markdown(
    """
    <style>
    /* Overall page */
    .main {
        background-color: #fafafa;
    }

    /* Title area */
    h1 {
        font-weight: 800 !important;
        letter-spacing: -0.5px;
        color: #0f172a !important;
    }

    /* Intro markdown block */
    .intro-box {
        background: linear-gradient(135deg, #f0fdf4 0%, #eff6ff 100%);
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 26px;
        margin-bottom: 22px;
    }
    .intro-box p {
        font-size: 16px;
        color: #334155;
        margin-bottom: 10px;
    }
    .intro-box ul {
        margin: 0;
        padding-left: 20px;
    }
    .intro-box li {
        color: #475569;
        font-size: 15px;
        margin-bottom: 4px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
    }
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] .stMarkdown p strong {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #334155;
    }

    /* Sidebar section headers */
    .sidebar-section {
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8 !important;
        margin-top: 18px;
        margin-bottom: 6px;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    div[data-testid="stMetricLabel"] {
        font-weight: 600;
        color: #64748b;
    }
    div[data-testid="stMetricValue"] {
        color: #0f172a;
    }

    /* Section headers in main body */
    h2 {
        color: #0f172a !important;
        font-weight: 700 !important;
        margin-top: 10px;
    }

    /* Pills widget (category / status selectors) */
    div[data-testid="stPills"] button {
        border-radius: 999px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# -------------------------------
# TITLE
# -------------------------------

st.title("🌐 Pakistan Cultural & Linguistic Atlas")

st.markdown(
    """
    <div class="intro-box">
    <p>Explore Pakistan's linguistic diversity and Sufi heritage through an interactive map.</p>
    <p style="margin-bottom:6px;"><strong>This digital atlas connects:</strong></p>
    <ul>
        <li>🗣️ Languages</li>
        <li>👥 Speaker populations</li>
        <li>⚠️ Endangerment status</li>
        <li>🕌 Historical Sufi poets</li>
        <li>🗺️ Cultural geography</li>
    </ul>
    </div>
    """,
    unsafe_allow_html=True
)


# -------------------------------
# LOAD DATA
# -------------------------------

REQUIRED_LANGUAGE_COLS = [
    "Language", "Category", "Family", "Province", "Speakers",
    "Script", "Endangerment_Status", "Description",
    "Latitude", "Longitude"
]

REQUIRED_POET_COLS = [
    "Name", "Birth", "Death", "Language", "Region",
    "Sufi_Order", "Famous_Work", "Description",
    "Latitude", "Longitude"
]


def normalize_columns(df):
    """Strip whitespace and normalize casing/spacing so small CSV
    formatting differences (e.g. ' category ', 'category') don't
    break the app."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def check_required_columns(df, required, file_label):
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(
            f"❌ **{file_label} is missing required column(s): "
            f"{', '.join(missing)}**\n\n"
            f"Columns found in the file: {list(df.columns)}\n\n"
            "Please check your CSV header row for typos, extra spaces, "
            "or a different delimiter (e.g. semicolon instead of comma)."
        )
        st.stop()


@st.cache_data
def load_data():

    base_path = os.path.dirname(__file__)

    language_file = os.path.join(base_path, "data", "languages.csv")
    poet_file = os.path.join(base_path, "data", "sufi_poets.csv")

    if not os.path.exists(language_file):
        st.error(f"❌ File not found: {language_file}")
        st.stop()

    if not os.path.exists(poet_file):
        st.error(f"❌ File not found: {poet_file}")
        st.stop()

    languages = pd.read_csv(language_file, encoding="utf-8-sig")
    poets = pd.read_csv(poet_file, encoding="utf-8-sig")

    languages = normalize_columns(languages)
    poets = normalize_columns(poets)

    return languages, poets


@st.cache_data
def load_provinces_geojson():
    """Load the local Pakistan provinces boundary file (data/pakistan_provinces.geojson)."""
    base_path = os.path.dirname(__file__)
    province_file = os.path.join(base_path, "data", "pakistan_provinces.geojson")

    if not os.path.exists(province_file):
        return None

    with open(province_file, "r", encoding="utf-8") as f:
        return json.load(f)


def match_provinces(province_text, all_province_names):
    """Map a free-text Province value from languages.csv (e.g. 'Southern Punjab',
    'Khyber Pakhtunkhwa and Punjab', 'All Pakistan') to one or more actual
    polygon province names."""
    if not isinstance(province_text, str):
        return []

    text = province_text.lower()

    if "all pakistan" in text:
        return list(all_province_names)

    matches = [
        name for name in all_province_names
        if name.lower() in text
    ]
    return matches


@st.cache_data
def load_pakistan_boundary():
    """Fetch Pakistan's national boundary polygon (cached) for map highlighting."""
    url = "https://raw.githubusercontent.com/datasets/geo-countries/main/data/countries.geojson"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        world = response.json()
    except Exception:
        return None

    pakistan_feature = next(
        (f for f in world["features"] if f["properties"].get("name") == "Pakistan"),
        None
    )

    if pakistan_feature is None:
        return None

    return {"type": "FeatureCollection", "features": [pakistan_feature]}


languages, poets = load_data()

check_required_columns(languages, REQUIRED_LANGUAGE_COLS, "languages.csv")
check_required_columns(poets, REQUIRED_POET_COLS, "sufi_poets.csv")

# Make sure numeric columns are actually numeric (guards against
# stray text, commas, or blank cells in the CSV).
languages["Speakers"] = pd.to_numeric(languages["Speakers"], errors="coerce").fillna(0)
languages["Latitude"] = pd.to_numeric(languages["Latitude"], errors="coerce")
languages["Longitude"] = pd.to_numeric(languages["Longitude"], errors="coerce")
poets["Latitude"] = pd.to_numeric(poets["Latitude"], errors="coerce")
poets["Longitude"] = pd.to_numeric(poets["Longitude"], errors="coerce")

# Drop rows with missing coordinates so the map doesn't error out.
languages = languages.dropna(subset=["Latitude", "Longitude"])
poets = poets.dropna(subset=["Latitude", "Longitude"])


# -------------------------------
# SIDEBAR FILTERS
# -------------------------------

st.sidebar.markdown("## 🔎 Explore Atlas")

st.sidebar.markdown("<div class='sidebar-section'>Language Category</div>", unsafe_allow_html=True)
all_categories = sorted(languages["Category"].dropna().unique())
category_filter = st.sidebar.pills(
    "Language Category",
    all_categories,
    selection_mode="multi",
    default=all_categories,
    label_visibility="collapsed"
)

st.sidebar.markdown("<div class='sidebar-section'>Endangerment Status</div>", unsafe_allow_html=True)
all_statuses = sorted(languages["Endangerment_Status"].dropna().unique())
status_filter = st.sidebar.pills(
    "Endangerment Status",
    all_statuses,
    selection_mode="multi",
    default=all_statuses,
    label_visibility="collapsed"
)

languages = languages[
    (languages["Category"].isin(category_filter)) &
    (languages["Endangerment_Status"].isin(status_filter))
]

st.sidebar.markdown("<div class='sidebar-section'>Search Language</div>", unsafe_allow_html=True)
search_language = st.sidebar.text_input(
    "Search Language",
    placeholder="e.g. Punjabi, Balochi...",
    label_visibility="collapsed"
)

if search_language:
    languages = languages[
        languages["Language"].str.contains(search_language, case=False, na=False)
    ]

st.sidebar.markdown("<div class='sidebar-section'>Search Sufi Poets</div>", unsafe_allow_html=True)
search_poet = st.sidebar.text_input(
    "Search Sufi Poet",
    placeholder="e.g. Bulleh Shah, Rehman Baba...",
    label_visibility="collapsed"
)

if search_poet:
    poets = poets[
        poets["Name"].str.contains(search_poet, case=False, na=False)
    ]

st.sidebar.caption(
    "Filters above apply to the Languages map and Sufi Poets search "
    "respectively — the two maps are shown on separate tabs."
)

st.sidebar.markdown("---")
st.sidebar.caption("🇵🇰 Pakistan Cultural & Linguistic Atlas")


# -------------------------------
# SHARED HELPERS
# -------------------------------

language_colors = {
    "National": "green",
    "Regional": "blue",
    "Endangered": "red"
}

chart_template = "plotly_white"
color_sequence = px.colors.qualitative.Set2

pakistan_boundary = load_pakistan_boundary()


def add_pakistan_boundary(map_obj):
    if pakistan_boundary:
        folium.GeoJson(
            pakistan_boundary,
            name="🇵🇰 Pakistan Boundary",
            style_function=lambda feature: {
                "fillColor": "#2ca25f",
                "color": "#006d2c",
                "weight": 3,
                "fillOpacity": 0.12,
            },
            highlight_function=lambda feature: {
                "fillOpacity": 0.28,
                "weight": 4,
            },
        ).add_to(map_obj)


# -------------------------------
# TABS: LANGUAGES vs SUFI POETS
# -------------------------------

lang_tab, poet_tab = st.tabs(["🗣️ Languages Map", "🕌 Sufi Poets Map"])


# ===============================
# LANGUAGES TAB
# ===============================

with lang_tab:

    st.subheader("Languages of Pakistan")

    language_map = folium.Map(
        location=[30.3753, 69.3451],
        zoom_start=5,
        tiles="CartoDB positron"
    )

    add_pakistan_boundary(language_map)

    language_group = folium.FeatureGroup(name="🗣️ Languages")

    for _, row in languages.iterrows():

        popup = f"""
        <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; min-width:220px;">
            <h4 style="margin-bottom:6px; color:#0f172a;">{row['Language']}</h4>
            <b>Category:</b> {row['Category']}<br>
            <b>Family:</b> {row['Family']}<br>
            <b>Province:</b> {row['Province']}<br>
            <b>Speakers:</b> {int(row['Speakers']):,}<br>
            <b>Script:</b> {row['Script']}<br>
            <b>Status:</b> {row['Endangerment_Status']}<br>
            <p style="margin-top:8px; color:#475569;">{row['Description']}</p>
        </div>
        """

        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=max(5, min(18, row["Speakers"] / 5000000)),
            color=language_colors.get(row["Category"], "purple"),
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup, max_width=350)
        ).add_to(language_group)

    language_group.add_to(language_map)
    folium.LayerControl(collapsed=False).add_to(language_map)

    st_folium(language_map, width=1200, height=600, key="language_map")

    # --- Language distribution choropleth ---
    st.divider()
    st.markdown("#### 🗺️ Language Distribution by Province")
    st.caption(
        "Select a language to see which provinces it is spoken in. "
        "Shading reflects that language's total speaker count wherever it appears "
        "(province-level data — not a per-district breakdown)."
    )

    provinces_geojson = load_provinces_geojson()

    if provinces_geojson is None:
        st.info(
            "Province boundary file not found. Add `data/pakistan_provinces.geojson` "
            "to your repo to enable this view."
        )
    else:
        all_province_names = sorted({
            feat["properties"]["Province"] for feat in provinces_geojson["features"]
        })

        # Use the full (unfiltered) language list for this selector so it isn't
        # affected by the sidebar filters above.
        full_languages, _ = load_data()
        full_languages["Speakers"] = pd.to_numeric(full_languages["Speakers"], errors="coerce").fillna(0)

        lang_col, stat_col = st.columns([2, 1])

        with lang_col:
            selected_language = st.selectbox(
                "Language",
                sorted(full_languages["Language"].dropna().unique()),
                index=0
            )

        lang_row = full_languages[full_languages["Language"] == selected_language].iloc[0]
        matched_provinces = match_provinces(lang_row["Province"], all_province_names)
        speaker_count = int(lang_row["Speakers"])

        with stat_col:
            st.metric(f"{selected_language} — Mother Tongue Speakers", f"{speaker_count:,}")

        province_values = pd.DataFrame({
            "Province": all_province_names,
            "Speakers": [speaker_count if p in matched_provinces else 0 for p in all_province_names]
        })

        fig_choropleth = px.choropleth(
            province_values,
            geojson=provinces_geojson,
            locations="Province",
            featureidkey="properties.Province",
            color="Speakers",
            color_continuous_scale="Blues",
            template="plotly_white"
        )
        fig_choropleth.update_geos(fitbounds="locations", visible=False)
        fig_choropleth.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            coloraxis_colorbar_title="Speakers"
        )

        st.plotly_chart(fig_choropleth, use_container_width=True)

    # --- Language statistics ---
    st.divider()
    st.markdown("#### 📊 Language Statistics")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Languages Displayed", len(languages))

    with col2:
        total_speakers = languages["Speakers"].sum()
        st.metric("Total Speakers", f"{int(total_speakers):,}")

    if len(languages) > 0:
        fig = px.pie(
            languages,
            names="Category",
            title="Languages by Category",
            template=chart_template,
            color_discrete_sequence=color_sequence,
            hole=0.4
        )
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(
            title_font_size=18,
            margin=dict(t=60, b=20, l=20, r=20),
            legend_title_text="Category"
        )
        st.plotly_chart(fig, use_container_width=True)


# ===============================
# SUFI POETS TAB
# ===============================

with poet_tab:

    st.subheader("Sufi Poets of Pakistan")

    poet_map = folium.Map(
        location=[30.3753, 69.3451],
        zoom_start=5,
        tiles="CartoDB positron"
    )

    add_pakistan_boundary(poet_map)

    poet_group = folium.FeatureGroup(name="🕌 Sufi Poets")

    for _, row in poets.iterrows():

        popup = f"""
        <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; min-width:220px;">
            <h4 style="margin-bottom:6px; color:#0f172a;">{row['Name']}</h4>
            <b>Period:</b> {row['Birth']} - {row['Death']}<br>
            <b>Language:</b> {row['Language']}<br>
            <b>Region:</b> {row['Region']}<br>
            <b>Sufi Order:</b> {row['Sufi_Order']}<br>
            <b>Famous Work:</b> {row['Famous_Work']}<br><br>
            <span style="color:#475569;">{row['Description']}</span>
        </div>
        """

        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=folium.Popup(popup, max_width=350),
            tooltip=row["Name"],
            icon=folium.Icon(icon="star", color="purple")
        ).add_to(poet_group)

    poet_group.add_to(poet_map)
    folium.LayerControl(collapsed=False).add_to(poet_map)

    st_folium(poet_map, width=1200, height=600, key="poet_map")

    # --- Poet statistics ---
    st.divider()
    st.markdown("#### 📊 Sufi Poet Statistics")

    st.metric("Sufi Poets Displayed", len(poets))

    if len(poets) > 0:
        fig2 = px.bar(
            poets,
            x="Language",
            title="Sufi Poets by Language",
            template=chart_template,
            color="Language",
            color_discrete_sequence=color_sequence
        )
        fig2.update_layout(
            title_font_size=18,
            showlegend=False,
            margin=dict(t=60, b=20, l=20, r=20),
            xaxis_title="",
            yaxis_title="Number of Poets"
        )
        st.plotly_chart(fig2, use_container_width=True)


# -------------------------------
# FOOTER
# -------------------------------

st.divider()
st.caption("Pakistan Cultural & Linguistic Atlas | Digital Humanities Project")
