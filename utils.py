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
import numpy as np
from matplotlib.font_manager import FontProperties
from PIL import Image, ImageDraw, ImageFont


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

def get_adaptive_fontsize(title, max_chars=20, base_size=40, min_size=14):
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

def plot_gpx_map(gdf, distances, elevations,name,date,num_dossard, padding_factor=0.2, size_border=2, basemap="OpenStreetMap.Mapnik",duree="", title="", fontname="DejaVu Sans", trace_color="red", border_color="red"):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4
    fig.subplots_adjust(left=0.05, right=0.95, top=0.98, bottom=0.05, hspace=0)
    gs = gridspec.GridSpec(2, 1, height_ratios=[0.74, 0.26])

    # Carte
    ax_map = fig.add_subplot(gs[0])
    gdf.plot(ax=ax_map, linewidth=3, color=trace_color)
    xmin, ymin, xmax, ymax = gdf.total_bounds
    width = xmax - xmin
    height = ymax - ymin
    #ajout padding pour que la trace ne touche pas les bords

    padding = padding_factor * max(width, height)
    if width > height:
        delta = (width - height) / 2
        ymin -= delta
        ymax += delta
    else:
        delta = (height - width) / 2
        xmin -= delta
        xmax += delta
    
    
    xmin -= padding
    xmax += padding
    ymin -= padding
    ymax += padding
    ax_map.set_xlim(xmin, xmax)
    ax_map.set_ylim(ymin, ymax)
    ax_map.set_aspect("equal", adjustable="box")
    ax_map.set_axis_off()


    start_point = gdf.geometry[0].coords[0]
    end_point = gdf.geometry[0].coords[-1]
    ax_map.scatter([start_point[0]], [start_point[1]], s=8, facecolors='white', edgecolors=trace_color, linewidths=1, zorder=11)
    ax_map.scatter([end_point[0]], [end_point[1]], s=8, color=trace_color, zorder=11)
    rect = patches.Rectangle((xmin, ymin), xmax - xmin, ymax - ymin, linewidth=size_border, edgecolor=border_color, facecolor='none', zorder=10)
    ax_map.add_patch(rect)
    if isinstance(basemap, str):
        basemap_obj = ctx.providers.flatten()[basemap]
    else:
        basemap_obj = basemap
    ctx.add_basemap(ax_map, source=basemap_obj, crs=gdf.crs)

    font_prop = FontProperties(fname=fontname)
    if fontname == "Fonts/Antonio-VariableFont_wght.ttf":
        fontsize_title = 35
    elif fontname == "Fonts/RacingSansOne-Regular.ttf":
        fontsize_title = 30
    
    # Nouveau footer : 2 lignes, 3 colonnes puis 2 colonnes
    gs_footer = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[1], height_ratios=[0.45, 0.55], hspace=0.01)
    gs_footer_top = gridspec.GridSpecFromSubplotSpec(1, 3, subplot_spec=gs_footer[0], width_ratios=[0.4, 1.5, 0.4])
    gs_footer_bottom = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs_footer[1], width_ratios=[2, 1])

    # 📄 Colonne gauche : infos 1
    ax_info1 = fig.add_subplot(gs_footer_top[0])
    ax_info1.axis("off")
    dplus, dmoins = calculate_deniv(elevations)
    distance_total = round(distances[-1], 2)
    info_text1 = f"{date}\n{distance_total:.2f}KM\nD+ {dplus}m"
    ax_info1.text(0.05, 1.1, info_text1, ha="left", va="top", fontsize=16, fontproperties=font_prop,weight="bold", clip_on=False)

    # 🏔️ Colonne centrale : profil
    ax_elev = fig.add_subplot(gs_footer_top[1])
    ax_elev.plot(distances, elevations, color=trace_color, linewidth=3)
    ax_elev.axis("off")

    # 🧑‍🦱 Colonne droite : infos 2
    ax_info2 = fig.add_subplot(gs_footer_top[2])
    ax_info2.axis("off")
    info_text2 = f"{name}\n#{num_dossard}"
    ax_info2.text(0.95, 1.1, info_text2, ha="right", va="top", fontsize=16, fontproperties=font_prop, weight="bold", clip_on=False)

    # 🏷️ Ligne titre + temps : titre gauche (2 lignes), durée droite
    ax_title_left = fig.add_subplot(gs_footer_bottom[0])
    ax_title_right = fig.add_subplot(gs_footer_bottom[1])
    ax_title_left.axis("off")
    ax_title_right.axis("off")

    first_line, second_line = split_title_words(title.upper())

    ax_title_left.text(0.01, 0.6, first_line, ha="left", va="center", fontsize = fontsize_title, fontproperties=font_prop)
    ax_title_left.text(0.01, 0.3, second_line, ha="left", va="center", fontsize = fontsize_title, fontproperties=font_prop, weight="bold")

    ax_title_right.text(0.99, 0.3, duree, ha="right", va="center", fontsize=35, fontproperties=font_prop)

    return fig



def compose_single_page_pdf(gdf, distances, elevations,name,date,num_dossard, padding_factor=0.2, size_border=2, basemap="OpenStreetMap.Mapnik",duree="", title="", fontname="DejaVu Sans", trace_color="red", border_color="red"):
    

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        fig = plot_gpx_map(gdf, distances, elevations,name,date,num_dossard,padding_factor,size_border, basemap,duree, title, fontname, trace_color, border_color)

        # Enregistrer PDF
        with PdfPages(tmp.name) as pdf:
            pdf.savefig(fig, dpi=300)
        plt.close(fig)
        return tmp.name



def split_title_words(title, max_words_first_line=2):
    if title is None:
        return ""
    else:
        words = title.strip().split()
        if len(words) <= max_words_first_line:
            return "" "", title
        first_line = " ".join(words[:max_words_first_line])
        second_line = " ".join(words[max_words_first_line:])
    return first_line, second_line