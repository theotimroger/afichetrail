import streamlit as st
import gpxpy
import geopandas as gpd
import contextily as ctx
import matplotlib.pyplot as plt
from shapely.geometry import LineString
from matplotlib.backends.backend_pdf import PdfPages
import tempfile
import os
import xyzservices.providers as xyz
from xyzservices import TileProvider
import matplotlib.gridspec as gridspec
import matplotlib.patches as patches
import matplotlib.font_manager as fm
from utils import parse_gpx, process_gpx, calculate_deniv, plot_gpx_map, compose_single_page_pdf

# 🔑 Insère ici ta clé API Thunderforest
thunderforest_api_key = st.secrets.get("thunderforest_api_key", "")
jawg_api_key = st.secrets.get("jawg_api_key","")
maptiler_api_key = st.secrets.get("maptiler_api_key")

# 🗺️ Définition des fonds de carte (avec clé API pour Thunderforest)
BASEMAPS = {
    "OpenStreetMap.Mapnik": "OpenStreetMap.Mapnik",
    "CartoDB.Positron": "CartoDB.Positron",
    "OpenTopoMap": "OpenTopoMap",
}

if maptiler_api_key:
    BASEMAPS["MapTiler Aquarelle"] = TileProvider(
        name="MapTiler.Aquarelle",
        url=f"https://api.maptiler.com/maps/aquarelle/256/{{z}}/{{x}}/{{y}}.png?key={maptiler_api_key}",
        attribution='&copy; <a href="https://www.maptiler.com/">MapTiler</a>, &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors',
        tile_size=256,
        max_zoom=22
    )

    BASEMAPS["MapTiler Backdrop"] = TileProvider(
        name="MapTiler.Backdrop",
        url=f"https://api.maptiler.com/maps/backdrop/256/{{z}}/{{x}}/{{y}}.png?key={maptiler_api_key}",
        attribution='&copy; <a href="https://www.maptiler.com/">MapTiler</a>, &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors',
        tile_size=256,
        max_zoom=22
    )

    BASEMAPS["MapTiler Landscape"] = TileProvider(
        name="MapTiler.Landscape",
        url=f"https://api.maptiler.com/maps/landscape/256/{{z}}/{{x}}/{{y}}.png?key={maptiler_api_key}",
        attribution='&copy; <a href="https://www.maptiler.com/">MapTiler</a>, &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors',
        tile_size=256,
        max_zoom=22
    )

    BASEMAPS["MapTiler Ocean"] = TileProvider(
        name="MapTiler.Ocean",
        url=f"https://api.maptiler.com/maps/ocean/256/{{z}}/{{x}}/{{y}}.png?key={maptiler_api_key}",
        attribution='&copy; <a href="https://www.maptiler.com/">MapTiler</a>, &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors',
        tile_size=256,
        max_zoom=22
    )


if thunderforest_api_key:
    BASEMAPS["Thunderforest Outdoors"] = TileProvider(
        name="Thunderforest.Outdoors",
        url=f"https://tile.thunderforest.com/outdoors/{{z}}/{{x}}/{{y}}.png?apikey={thunderforest_api_key}",
        attribution="Maps © Thunderforest, Data © OpenStreetMap contributors",
        max_zoom=22,
        tile_size=256
    )
    BASEMAPS["Thunderforest MobileAtlas"] = TileProvider(
    name="Thunderforest.MobileAtlas",
    url=f"https://tile.thunderforest.com/mobile-atlas/{{z}}/{{x}}/{{y}}.png?apikey={thunderforest_api_key}",
	attribution= "Maps © Thunderforest, Data © OpenStreetMap contributors",
	max_zoom = 40,
    tile_size=256
    )


if jawg_api_key:
    BASEMAPS["Jawg Custom"] = TileProvider(
        name="Jawg.Custom",
        url=f"https://tile.jawg.io/d309c69f-1d6f-40d9-8a18-da8dc137f711/{{z}}/{{x}}/{{y}}{{r}}.png?access-token={jawg_api_key}",
        attribution='Maps © Jawg, Data ©OpenStreetMap contributors',
        max_zoom=22,
        tile_size=256
    )


# 🚀 Interface Streamlit
st.set_page_config(page_title="GPX vers PDF", layout="centered")
st.title("🗺️ Création d'affiche pour votre Trail")

uploaded_file = st.file_uploader("📂 Charge ton fichier GPX", type=["gpx"])

if "example_path" not in st.session_state:
    st.session_state.example_path = None
if "gpx_content" not in st.session_state:
    st.session_state.gpx_content = None

if st.button("📄 Utiliser un exemple (Tour des Glaciers de la Vanoise)"):
    example_path = os.path.join("Exemple/Tour_des_glaciers_de_la_Vanoise.gpx")
    try:
        with open(example_path, "rb") as f:
            st.session_state.example_path = example_path
            st.success("✅ Fichier d'exemple chargé.")
    except FileNotFoundError:
        st.error("❌ Fichier d'exemple introuvable.")

if uploaded_file:
    st.session_state.gpx_content = uploaded_file.read().decode("utf-8")
    gpx_content = st.session_state.gpx_content
    distances, elevations, _, coords = process_gpx(gpx_content)
    distance_km = round(distances[-1], 2) if distances else 0
    dplus, dmoins = calculate_deniv(elevations)
    st.success("✅ Fichier GPX utilisateur chargé.")

elif st.session_state.example_path:
    with open(st.session_state.example_path, "rb") as f:
            gpx_content = f.read().decode("utf-8")
    distances, elevations, _, coords = process_gpx(gpx_content)
    distance_km = round(distances[-1], 2) if distances else 0
    dplus, dmoins = calculate_deniv(elevations)

with st.sidebar:
    date_race = st.text_input("Date", value="", label_visibility="visible")

    nom = st.text_input("Nom", value="", label_visibility="visible")

    duree = st.text_input("Temps", value="", label_visibility="visible")

    num_dossard = st.text_input("# Dossard", value="")

    selected_basemap = st.selectbox("🗺️ Choisis un fond de carte", list(BASEMAPS.keys()))
    custom_title = st.text_input("🖊️ Titre personnalisé pour la carte", value="")


    # Liste souhaitée
    preferred_fonts = [
    "Fonts/Antonio-VariableFont_wght.ttf", "Fonts/RacingSansOne-Regular.ttf"
    ]

    # On vérifie celles qui existent vraiment sur l'environnement
    # Liste complète des polices disponibles
    #all_fonts = sorted(set(f.name for f in fm.fontManager.ttflist))

    # Sélecteur dans Streamlit
    font_choice = st.selectbox(
        "✒️ Choisissez une police parmi celles installées :", 
        options=preferred_fonts
    )

    # 🎨 Personnalisation des couleurs
    col1, col2 = st.columns(2)

    with col1:
        trace_color = st.color_picker("🟥 Couleur de la trace GPX", value="#000000")

    with col2:
        border_color = st.color_picker("⬛ Couleur du cadre de la carte", value="#FFFFFF")

    padding_factor = st.slider("Sélectionnez une valeur de padding", min_value=0.0, max_value=0.5, step=0.05)
    size_border = st.slider("Sélectionnez une taille pour les bords", min_value=0, max_value=20, step=1)

if uploaded_file is not None:
    uploaded_file.seek(0)
    gdf = parse_gpx(uploaded_file)
    if gdf is None:
        st.error("❌ Aucune trace trouvée dans le fichier.")
    else:
        st.success("✅ Trace GPX chargée avec succès.")
        fig = plot_gpx_map(gdf,
            distances,
            elevations,
            name = nom,
            date = date_race,
            num_dossard=num_dossard,
            padding_factor=padding_factor,
            size_border=size_border,
            basemap=BASEMAPS[selected_basemap],
            duree=duree,
            title=custom_title,
            fontname=font_choice,
            trace_color=trace_color,
            border_color=border_color)

        st.pyplot(fig)

        if st.button("📄 Générer le PDF"):
            pdf_path = compose_single_page_pdf( 
            gdf,
            distances,
            elevations,
            name = nom,
            date = date_race,
            num_dossard=num_dossard,
            basemap=BASEMAPS[selected_basemap],
            duree=duree,
            title=custom_title,
            fontname=font_choice,
            trace_color=trace_color,
            border_color=border_color
            )
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="⬇️ Télécharger le PDF",
                    data=f,
                    file_name="trace_map.pdf",
                    mime="application/pdf"
                )

elif st.session_state.example_path is not None:
    with open(st.session_state.example_path, "rb") as f:
        gdf = parse_gpx(f)
    if gdf is None:
        st.error("❌ Aucune trace trouvée dans le fichier.")
    else:
        st.success("✅ Trace GPX chargée avec succès.")
        fig = plot_gpx_map(gdf,
            distances,
            elevations,
            name = nom,
            date = date_race,
            num_dossard=num_dossard,
            padding_factor=padding_factor,
            size_border=size_border,
            basemap=BASEMAPS[selected_basemap],
            duree=duree,
            title=custom_title,
            fontname=font_choice,
            trace_color=trace_color,
            border_color=border_color)

        st.pyplot(fig)

        if st.button("📄 Générer le PDF"):
            pdf_path = compose_single_page_pdf( 
            gdf,
            distances,
            elevations,
            name = nom,
            date = date_race,
            num_dossard=num_dossard,
            basemap=BASEMAPS[selected_basemap],
            duree=duree,
            title=custom_title,
            fontname=font_choice,
            trace_color=trace_color,
            border_color=border_color
            )
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="⬇️ Télécharger le PDF",
                    data=f,
                    file_name="trace_map.pdf",
                    mime="application/pdf"
                )
