import streamlit as st
import requests
import re
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from PIL import Image

from io import BytesIO
import time


BASE_URL = "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/png_masked/"

# full PNG image extent from CHMI documentation
PNG_EXTENT = [11.267, 20.770, 48.047, 52.167]


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

@st.cache_resource
def load_border_overlay():
    return Image.open("border_overlay.png").convert("RGBA")

@st.cache_resource
def build_combined_frames(frames, border_overlay):
    combined_frames = []

    for radar_img in frames:
        radar_img = radar_img.convert("RGBA")

        white_bg = Image.new("RGBA", radar_img.size, "white")
        white_bg.paste(radar_img, (0, 0), radar_img)

        overlay = border_overlay.resize(radar_img.size)

        combined = Image.alpha_composite(white_bg, overlay)

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

radar_files = get_latest_radar_files()

if not radar_files:
    st.error("Nepodařilo se načíst radarová data.")
    st.stop()

file_urls = [BASE_URL + f for f in radar_files]
frames = load_radar_images(file_urls)
combined_frames = build_combined_frames(frames, border_overlay)

gif_data = build_gif(combined_frames)

st.image(gif_data, use_container_width=True)
