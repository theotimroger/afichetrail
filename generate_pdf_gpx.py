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

# 🗺️ Définition des fonds de carte (avec clé API pour Thunderforest)
BASEMAPS = {
    "OpenStreetMap.Mapnik": "OpenStreetMap.Mapnik",
    "CartoDB.Positron": "CartoDB.Positron",
    "OpenTopoMap": "OpenTopoMap",
}

if thunderforest_api_key:
    BASEMAPS["Thunderforest Outdoors"] = TileProvider(
        name="Thunderforest.Outdoors",
        url=f"https://tile.thunderforest.com/outdoors/{{z}}/{{x}}/{{y}}.png?apikey={thunderforest_api_key}",
        attribution="Maps © Thunderforest, Data © OpenStreetMap contributors",
        max_zoom=22,
        tile_size=256
    )



# 🚀 Interface Streamlit
st.set_page_config(page_title="GPX vers PDF", layout="centered")
st.title("🗺️ Générateur de carte PDF à partir d’un fichier GPX")

uploaded_file = st.file_uploader("📂 Charge ton fichier GPX", type=["gpx"])
if uploaded_file is not None:
    gpx_content = uploaded_file.read().decode("utf-8")
    distances, elevations, _, coords = process_gpx(gpx_content)
    distance_km = round(distances[-1], 2) if distances else 0
    dplus, dmoins = calculate_deniv(elevations)

st.markdown(
            """
            <div style="display: flex; align-items: center; justify-content: flex-start; height: 40px;">
                <p style="font-weight: bold; margin: 0;">Date</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
date_race = st.text_input("", value="01.01.1900", label_visibility="collapsed")

st.markdown(
            """
            <div style="display: flex; align-items: center; justify-content: flex-start; height: 40px;">
                <p style="font-weight: bold; margin: 0;">Nom</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
nom = st.text_input("", value="Jules Martin", label_visibility="collapsed")

st.markdown(
            """
            <div style="display: flex; align-items: center; justify-content: flex-start; height: 40px;">
                <p style="font-weight: bold; margin: 0;">Durée</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
duree = st.text_input("", value="00:00:00", label_visibility="collapsed")
selected_basemap = st.selectbox("🗺️ Choisis un fond de carte", list(BASEMAPS.keys()))
custom_title = st.text_input("🖊️ Titre personnalisé pour la carte (facultatif)", value="")


# Liste souhaitée
preferred_fonts = [
    "DejaVu Sans", "Arial", "Times New Roman", "Courier New",
    "Comic Sans MS", "Georgia", "Trebuchet MS", "Verdana",
    "Impact", "Lucida Console", "Arial Black", "DIN Alternate"
]

# On vérifie celles qui existent vraiment sur l'environnement
# Liste complète des polices disponibles
all_fonts = sorted(set(f.name for f in fm.fontManager.ttflist))

# Sélecteur dans Streamlit
font_choice = st.selectbox(
    "✒️ Choisissez une police parmi celles installées :", 
    options=all_fonts
)
# Afficher un aperçu de la police sélectionnée

fig, ax = plt.subplots(figsize=(6, 0.8))  # figure fine en hauteur
ax.text(0.5, 0.5, custom_title, fontsize=18, fontname=font_choice,
        ha='center', va='center')

ax.axis('off')
plt.subplots_adjust(left=0, right=1, top=1, bottom=0)  # aucune marge

st.pyplot(fig)

# 🎨 Personnalisation des couleurs
col1, col2 = st.columns(2)

with col1:
    trace_color = st.color_picker("🟥 Couleur de la trace GPX", value="#FF0000")

with col2:
    border_color = st.color_picker("⬛ Couleur du cadre de la carte", value="#FF0000")



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
            basemap=BASEMAPS[selected_basemap],
            duree=duree,
            title=custom_title or uploaded_file.name,
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
            basemap=BASEMAPS[selected_basemap],
            duree=duree,
            title=custom_title or uploaded_file.name,
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
