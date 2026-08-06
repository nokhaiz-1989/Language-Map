import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
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
# TITLE
# -------------------------------

st.title("🌐 Pakistan Cultural & Linguistic Atlas")

st.markdown(
"""
Explore Pakistan's linguistic diversity and Sufi heritage through an interactive map.

This digital atlas connects:
- Languages
- Speaker populations
- Endangerment status
- Historical Sufi poets
- Cultural geography
"""
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

st.sidebar.header("🔎 Explore Atlas")


layer_choice = st.sidebar.multiselect(
    "Select Map Layers",
    [
        "Languages",
        "Sufi Poets"
    ],
    default=[
        "Languages",
        "Sufi Poets"
    ]
)



if "Languages" in layer_choice:

    category_filter = st.sidebar.multiselect(
        "Language Category",
        sorted(languages["Category"].dropna().unique()),
        default=sorted(languages["Category"].dropna().unique())
    )


    status_filter = st.sidebar.multiselect(
        "Endangerment Status",
        sorted(languages["Endangerment_Status"].dropna().unique()),
        default=sorted(languages["Endangerment_Status"].dropna().unique())
    )


    languages = languages[
        (languages["Category"].isin(category_filter)) &
        (languages["Endangerment_Status"].isin(status_filter))
    ]



search_language = st.sidebar.text_input(
    "Search Language"
)


if search_language:

    languages = languages[
        languages["Language"]
        .str.contains(
            search_language,
            case=False,
            na=False
        )
    ]



# -------------------------------
# CREATE MAP
# -------------------------------


pakistan_map = folium.Map(
    location=[30.3753, 69.3451],
    zoom_start=5,
    tiles="OpenStreetMap"
)



# -------------------------------
# LANGUAGE COLORS
# -------------------------------

language_colors = {

    "National": "green",

    "Regional": "blue",

    "Endangered": "red"

}



# -------------------------------
# LANGUAGE LAYER
# -------------------------------


if "Languages" in layer_choice:

    language_group = folium.FeatureGroup(
        name="🗣️ Languages"
    )


    for _, row in languages.iterrows():

        popup = f"""

        <h4>{row['Language']}</h4>

        <b>Category:</b> {row['Category']}<br>

        <b>Family:</b> {row['Family']}<br>

        <b>Province:</b> {row['Province']}<br>

        <b>Speakers:</b> {int(row['Speakers']):,}<br>

        <b>Script:</b> {row['Script']}<br>

        <b>Status:</b> {row['Endangerment_Status']}<br>

        <p>
        {row['Description']}
        </p>

        """


        folium.CircleMarker(

            location=[
                row["Latitude"],
                row["Longitude"]
            ],

            radius=max(
                5,
                min(
                    18,
                    row["Speakers"] / 5000000
                )
            ),

            color=language_colors.get(
                row["Category"],
                "purple"
            ),

            fill=True,

            fill_opacity=0.7,

            popup=folium.Popup(
                popup,
                max_width=350
            )

        ).add_to(language_group)


    language_group.add_to(pakistan_map)




# -------------------------------
# SUFI POET LAYER
# -------------------------------


if "Sufi Poets" in layer_choice:


    poet_group = folium.FeatureGroup(
        name="🕌 Sufi Poets"
    )


    for _, row in poets.iterrows():

        popup = f"""

        <h4>{row['Name']}</h4>

        <b>Period:</b>
        {row['Birth']} - {row['Death']}
        <br>

        <b>Language:</b>
        {row['Language']}
        <br>

        <b>Region:</b>
        {row['Region']}
        <br>

        <b>Sufi Order:</b>
        {row['Sufi_Order']}
        <br>

        <b>Famous Work:</b>
        {row['Famous_Work']}
        <br><br>

        {row['Description']}

        """


        folium.Marker(

            location=[
                row["Latitude"],
                row["Longitude"]
            ],

            popup=folium.Popup(
                popup,
                max_width=350
            ),

            tooltip=row["Name"],

            icon=folium.Icon(
                icon="star",
                color="purple"
            )

        ).add_to(poet_group)



    poet_group.add_to(pakistan_map)



# -------------------------------
# ADD MAP CONTROL
# -------------------------------

folium.LayerControl().add_to(
    pakistan_map
)



# -------------------------------
# DISPLAY MAP
# -------------------------------


st_folium(

    pakistan_map,

    width=1200,

    height=650

)




# -------------------------------
# STATISTICS
# -------------------------------

st.divider()

st.header("📊 Cultural Statistics")


col1, col2, col3 = st.columns(3)



with col1:

    st.metric(
        "Languages Displayed",
        len(languages)
    )



with col2:

    st.metric(
        "Sufi Poets Displayed",
        len(poets)
    )



with col3:

    total_speakers = languages["Speakers"].sum()

    st.metric(
        "Total Speakers",
        f"{int(total_speakers):,}"
    )




# -------------------------------
# CHARTS
# -------------------------------


if len(languages) > 0:


    fig = px.pie(

        languages,

        names="Category",

        title="Languages by Category"

    )


    st.plotly_chart(
        fig,
        use_container_width=True
    )



if len(poets) > 0:


    fig2 = px.bar(

        poets,

        x="Language",

        title="Sufi Poets by Language"

    )


    st.plotly_chart(
        fig2,

        use_container_width=True

    )



# -------------------------------
# FOOTER
# -------------------------------

st.caption(
"""
Pakistan Cultural & Linguistic Atlas | Digital Humanities Project
"""
)
