import streamlit as st
import requests
import re
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from PIL import Image

import geopandas as gpd

from io import BytesIO
import time


BASE_URL = "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/png_masked/"

# full PNG image extent from CHMI documentation
PNG_EXTENT = [11.267, 20.770, 48.047, 52.167]


@st.cache_data(ttl=60, show_spinner=False)
def get_latest_radar_files(n=10):
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


@st.cache_data(ttl=60, show_spinner=False)
def load_radar_images(file_urls):
    images = []
    session = requests.Session()

    for url in file_urls:
        response = session.get(url, timeout=10)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGBA")
        images.append(img)

    return images


@st.cache_data(show_spinner=False)
def load_kraje():
    gdf = gpd.read_file("kraje_wgs84.geojson")
    gdf["geometry"] = gdf.geometry.simplify(0.013, preserve_topology=True)
    return gdf.geometry


border_layer = Image.new("RGBA", frames[0].size, (0, 0, 0, 0))


def format_time(filename):
    ts = filename.split(".")[2] + filename.split(".")[3]
    dt = datetime.strptime(ts, "%Y%m%d%H%M")
    dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Prague"))

    return dt.strftime("%d.%m. %H:%M")


kraje = load_kraje()

radar_files = get_latest_radar_files()

if not radar_files:
    st.error("Nepodařilo se načíst radarová data.")
    st.stop()

file_urls = [BASE_URL + f for f in radar_files]
frames = load_radar_images(file_urls)


if "playing" not in st.session_state:
    st.session_state.playing = False

if "frame_idx" not in st.session_state:
    st.session_state.frame_idx = len(frames) - 1

if st.button("▶ Play / Pause"):
    st.session_state.playing = not st.session_state.playing

if st.session_state.playing:
    st.session_state.frame_idx = (
        st.session_state.frame_idx + 1
    ) % len(frames)

    time.sleep(0.4)
    st.rerun()

image_placeholder = st.empty()

radar_img = frames[st.session_state.frame_idx].convert("RGBA")

combined = Image.alpha_composite(
    border_layer,
    radar_img
)

image_placeholder.image(combined, use_container_width=True)

