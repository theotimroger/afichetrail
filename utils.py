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


# 📍 Fonctions principales
def parse_gpx(uploaded_file):
    gpx_content = uploaded_file.read().decode("utf-8")
    gpx = gpxpy.parse(gpx_content)
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append((point.longitude, point.latitude))
    if not points:
        return None
    gdf = gpd.GeoDataFrame(geometry=[LineString(points)], crs="EPSG:4326")
    return gdf.to_crs(epsg=3857)

def process_gpx(gpx_content):
    """Lis le fichier GPX et retourne distances, elevations, etc."""
    gpx = gpxpy.parse(gpx_content)

    last_point = None
    total_distance = 0
    distances = []
    elevations = []
    coords = []

    DISTANCE_MIN = 30  # mètres entre 2 points retenus
    distance_since_last_save = 0

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                coords.append((point.latitude, point.longitude))
                if last_point is not None:
                    d = point.distance_3d(last_point) or 0
                    total_distance += d
                    distance_since_last_save += d

                    if distance_since_last_save >= DISTANCE_MIN:
                        distances.append(total_distance / 1000)  # en km
                        elevations.append(point.elevation)
                        distance_since_last_save = 0  # reset après avoir sauvé
                else:
                    # Sauvegarder tout premier point
                    distances.append(total_distance / 1000)
                    elevations.append(point.elevation)

                last_point = point

    distances_pace = [(distances[i] + distances[i-1]) / 2 for i in range(1, len(distances))]

    return distances, elevations, distances_pace, coords

def get_adaptive_fontsize(title, max_chars=30, base_size=40, min_size=14):
    """
    Calcule dynamiquement une taille de police en fonction de la longueur du titre.
    """
    length = len(title)
    if length <= max_chars:
        return base_size
    scale = max_chars / length
    return max(min_size, int(base_size * scale))

def calculate_deniv(elevations):
    d_plus = [0]
    d_moins = [0]
    for i in range(1,len(elevations)):
        deniv_segment = elevations[i]-elevations[i-1]
        if deniv_segment > 0:
            d_plus.append(d_plus[-1]+deniv_segment)
            d_moins.append(d_moins[-1])
        else:
            d_plus.append(d_plus[-1])
            d_moins.append(d_moins[-1]+deniv_segment)
    return round(d_plus[-1]), round(d_moins[-1])

def plot_gpx_map(gdf, distances, elevations,name,date, basemap,duree="", title="", fontname="DejaVu Sans", trace_color="red", border_color="red"):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4
    fig.subplots_adjust(left=0.05, right=0.95, top=0.98, bottom=0.05, hspace = 0.1)
    gs = gridspec.GridSpec(3, 1, height_ratios=[0.05, 0.70, 0.25])

    # Titre
    ax_title = fig.add_subplot(gs[0])
    ax_title.axis("off")

    titre_affiche = title.upper()
    fontsize = get_adaptive_fontsize(titre_affiche)

    ax_title.text(
        0.5, 0.5, titre_affiche,
        ha="center", va="center",
        fontsize=fontsize,
        fontname=fontname
    )

    # Carte
    ax_map = fig.add_subplot(gs[1])
    gdf.plot(ax=ax_map, linewidth=2, color=trace_color)

    # Forcer carré + ajouter un padding (12 % de marge)
    xmin, ymin, xmax, ymax = gdf.total_bounds
    width = xmax - xmin
    height = ymax - ymin
    padding = 0.2 * max(width, height)  # 12% d’espace

    if width > height:
        delta = (width - height) / 2
        ymin -= delta
        ymax += delta
    else:
        delta = (height - width) / 2
        xmin -= delta
        xmax += delta

    # Appliquer le padding sur tous les côtés
    xmin -= padding
    xmax += padding
    ymin -= padding
    ymax += padding

    ax_map.set_xlim(xmin, xmax)
    ax_map.set_ylim(ymin, ymax)
    ax_map.set_aspect("equal", adjustable="box")
    ax_map.set_axis_off()
    # Points de départ et d'arrivée
    start_point = gdf.geometry[0].coords[0]
    end_point = gdf.geometry[0].coords[-1]

    # Départ : cercle avec bord couleur trace et fond blanc
    ax_map.scatter(
        [start_point[0]], [start_point[1]],
        s=8, facecolors='white', edgecolors=trace_color, linewidths=1, zorder=11
    )

    # Arrivée : cercle plein couleur trace
    ax_map.scatter(
        [end_point[0]], [end_point[1]],
        s=8, color=trace_color, zorder=11
    )

            # Dessiner un cadre autour de la carte
    rect = patches.Rectangle(
        (xmin, ymin),
        xmax - xmin,
        ymax - ymin,
        linewidth=2,
        edgecolor=border_color,  # même couleur que la trace
        facecolor='none',
        zorder=10  # au-dessus du fond de carte
    )
    ax_map.add_patch(rect)


    # Ici : ajout du fond de carte à `ax_map`
    if isinstance(basemap, str):
        basemap_obj = ctx.providers.flatten()[basemap]
    else:
        basemap_obj = basemap

    ctx.add_basemap(ax_map, source=basemap_obj, crs=gdf.crs)

    # Infos supplémentaires en bas
    # --- Bas de page : Infos + Profil Altimétrique ---
    gs_footer = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[2], height_ratios=[0.3, 0.7])

    # 📄 Texte d'infos
    ax_info = fig.add_subplot(gs_footer[0])
    ax_info.axis("off")
    dplus, dmoins = calculate_deniv(elevations)
    distance_total = round(distances[-1], 2)
    footer_text = f"{name} | {date} \nDistance : {distance_total} km| D+ : {dplus} m | D- : {abs(dmoins)} m \n{duree}"
    ax_info.text(0.5, 0.5, footer_text, ha="center", va="center", fontsize=13, fontname=fontname)

    # ⛰️ Profil altimétrique
    ax_elev = fig.add_subplot(gs_footer[1])
    ax_elev.plot(distances, elevations, color=trace_color, linewidth=1.5)
    ax_elev.axis("off")


def compose_single_page_pdf(gdf, distances, elevations,name,date, basemap,duree="", title="", fontname="DejaVu Sans", trace_color="red", border_color="red"):
    

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        fig = plt.figure(figsize=(8.27, 11.69))  # A4
        fig.subplots_adjust(left=0.05, right=0.95, top=0.98, bottom=0.05, hspace = 0.1)
        gs = gridspec.GridSpec(3, 1, height_ratios=[0.05, 0.70, 0.25])

        # Titre
        ax_title = fig.add_subplot(gs[0])
        ax_title.axis("off")

        titre_affiche = title.upper()
        fontsize = get_adaptive_fontsize(titre_affiche)

        ax_title.text(
            0.5, 0.5, titre_affiche,
            ha="center", va="center",
            fontsize=fontsize,
            fontname=fontname
        )

        # Carte
        ax_map = fig.add_subplot(gs[1])
        gdf.plot(ax=ax_map, linewidth=2, color=trace_color)

        # Forcer carré + ajouter un padding (12 % de marge)
        xmin, ymin, xmax, ymax = gdf.total_bounds
        width = xmax - xmin
        height = ymax - ymin
        padding = 0.2 * max(width, height)  # 12% d’espace

        if width > height:
            delta = (width - height) / 2
            ymin -= delta
            ymax += delta
        else:
            delta = (height - width) / 2
            xmin -= delta
            xmax += delta

        # Appliquer le padding sur tous les côtés
        xmin -= padding
        xmax += padding
        ymin -= padding
        ymax += padding

        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)
        ax_map.set_aspect("equal", adjustable="box")
        ax_map.set_axis_off()
        # Points de départ et d'arrivée
        start_point = gdf.geometry[0].coords[0]
        end_point = gdf.geometry[0].coords[-1]

        # Départ : cercle avec bord couleur trace et fond blanc
        ax_map.scatter(
            [start_point[0]], [start_point[1]],
            s=8, facecolors='white', edgecolors=trace_color, linewidths=1, zorder=11
        )

        # Arrivée : cercle plein couleur trace
        ax_map.scatter(
            [end_point[0]], [end_point[1]],
            s=8, color=trace_color, zorder=11
        )

                # Dessiner un cadre autour de la carte
        rect = patches.Rectangle(
            (xmin, ymin),
            xmax - xmin,
            ymax - ymin,
            linewidth=2,
            edgecolor=border_color,  # même couleur que la trace
            facecolor='none',
            zorder=10  # au-dessus du fond de carte
        )
        ax_map.add_patch(rect)


        # Ici : ajout du fond de carte à `ax_map`
        if isinstance(basemap, str):
            basemap_obj = ctx.providers.flatten()[basemap]
        else:
            basemap_obj = basemap

        ctx.add_basemap(ax_map, source=basemap_obj, crs=gdf.crs)

        # Infos supplémentaires en bas
        # --- Bas de page : Infos + Profil Altimétrique ---
        gs_footer = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[2], height_ratios=[0.3, 0.7])

        # 📄 Texte d'infos
        ax_info = fig.add_subplot(gs_footer[0])
        ax_info.axis("off")
        dplus, dmoins = calculate_deniv(elevations)
        distance_total = round(distances[-1], 2)
        footer_text = f"{name} | {date} \nDistance : {distance_total} km| D+ : {dplus} m | D- : {abs(dmoins)} m \n{duree}"
        ax_info.text(0.5, 0.5, footer_text, ha="center", va="center", fontsize=13, fontname=fontname)

        # ⛰️ Profil altimétrique
        ax_elev = fig.add_subplot(gs_footer[1])
        ax_elev.plot(distances, elevations, color=trace_color, linewidth=1.5)
        ax_elev.axis("off")
        

        # Enregistrer PDF
        with PdfPages(tmp.name) as pdf:
            pdf.savefig(fig)
        plt.close(fig)
        return tmp.name
    