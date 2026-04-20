import streamlit as st
import requests
import re
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

import time


st.set_page_config(
    page_title="Radar (open data ČHMÚ)",  # this changes the browser tab title
    page_icon="⛈️"                     # optional: emoji or path to an image
)

BASE_URL = "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/png_masked/"

# full PNG image extent from CHMI documentation
FULL_EXTENT = [11.267, 20.770, 48.047, 52.167]
DATA_EXTENT = [11.267, 19.624, 48.047, 51.458]

MARKERS = [
    (16.1113, 49.0546),   # first place
    (16.5642, 49.2147)    # second place
]

@st.cache_data(ttl=60, show_spinner=False)
def get_latest_radar_files(n=20):
    try:
        response = requests.get(BASE_URL, timeout=10)
        response.raise_for_status()

        pattern = re.compile(
            r"pacz2gmaps3\.z_max3d\.(\d{8}\.\d{4})\.0\.png"
        )

        matches = pattern.findall(response.text)

        if not matches:
            return []

        latest = sorted(matches)[-n:]

        return [
            f"pacz2gmaps3.z_max3d.{ts}.0.png"
            for ts in latest
        ]

    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner="Načítám data...")
def load_radar_images(file_urls):
    images = []
    session = requests.Session()

    for url in file_urls:
        response = session.get(url, timeout=10)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGBA")
        images.append(img)

    return images

@st.cache_resource
def load_border_overlay():
    return Image.open("border_overlay.png").convert("RGBA")

@st.cache_resource
def load_terrain():
    return Image.open("terrain_data.png").convert("RGBA")

def lonlat_to_pixel(extent, lon, lat, width, height):
    x = int((lon - extent[0]) / (extent[1] - extent[0]) * width)
    y = int((extent[3] - lat) / (extent[3] - extent[2]) * height)
    return x, y

@st.cache_resource
def build_combined_frames(frames, terrain, border_overlay):
    combined_frames = []

    for radar_img in frames:
        radar_img = radar_img.convert("RGBA")
        width, height = radar_img.size

        base = Image.new("RGBA", radar_img.size, "white")

        x1, y1 = lonlat_to_pixel(FULL_EXTENT, DATA_EXTENT[0], DATA_EXTENT[3], width, height)
        x2, y2 = lonlat_to_pixel(FULL_EXTENT, DATA_EXTENT[1], DATA_EXTENT[2], width, height)

        map_w = x2 - x1
        map_h = y2 - y1

        terrain_small = terrain.resize((map_w, map_h))
        border_small = border_overlay.resize((map_w, map_h))

        base.paste(terrain_small, (x1, y1))

        base = Image.alpha_composite(base, radar_img)

        overlay_full = Image.new("RGBA", radar_img.size, (0, 0, 0, 0))
        overlay_full.paste(border_small, (x1, y1), border_small)

        combined = Image.alpha_composite(base, overlay_full)

        draw = ImageDraw.Draw(combined)

        for lon, lat in MARKERS:
            x, y = lonlat_to_pixel(FULL_EXTENT, lon, lat, width, height)

            size = 4
            draw.line((x - size, y, x + size, y), fill="#02ebdb", width=2)
            draw.line((x, y - size, x, y + size), fill="#02ebdb", width=2)

        combined_frames.append(combined)

    return combined_frames

@st.cache_resource
def build_gif(frames):
    buf = BytesIO()

    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=400,
        loop=0
    )

    buf.seek(0)
    return buf.getvalue()

def format_time(filename):
    ts = filename.split(".")[2] + filename.split(".")[3]
    dt = datetime.strptime(ts, "%Y%m%d%H%M")
    dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Prague"))

    return dt.strftime("%d.%m. %H:%M")

border_overlay = load_border_overlay()
terrain = load_terrain()

if st.button("🔄 Aktualizovat radar"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

radar_files = get_latest_radar_files()

if not radar_files:
    st.error("Nepodařilo se načíst radarová data.")
    st.stop()

file_urls = [BASE_URL + f for f in radar_files]
frames = load_radar_images(file_urls)
combined_frames = build_combined_frames(frames, terrain, border_overlay)

gif_data = build_gif(combined_frames)

st.image(gif_data, use_container_width=True)
