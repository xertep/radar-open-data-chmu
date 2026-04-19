import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import h5py
import tempfile

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd


@st.cache_data(ttl=60, show_spinner=False)
def get_latest_radar_files(n=10):
    url = "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/hdf5/"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        pattern = re.compile(
            r"T_PABV23_C_OKPR_(\d{14})\.hdf"
        )

        matches = pattern.findall(response.text)

        if not matches:
            return []

        newest = max(matches)
        newest_dt = datetime.strptime(newest, "%Y%m%d%H%M%S")

        files = []
        for i in range(n):
            dt = newest_dt - timedelta(minutes=5 * i)
            ts = dt.strftime("%Y%m%d%H%M%S")

            filename = f"T_PABV23_C_OKPR_{ts}.hdf"
            files.append(filename)

        return files

    except Exception:
        return []

@st.cache_data(ttl=60, show_spinner=False)
def load_radar_batch(file_urls):
    frames = []
    session = requests.Session()

    for url in file_urls:
        response = session.get(url, timeout=10)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".hdf") as tmp:
            tmp.write(response.content)
            tmp.flush()

            with h5py.File(tmp.name, "r") as f:
                raw = f["dataset1/data1/data"][:]
                attrs = f["dataset1/data1/what"].attrs

                gain = attrs["gain"]
                offset = attrs["offset"]
                nodata = attrs["nodata"]
                undetect = attrs["undetect"]

                data = raw.astype(float)
                data[raw == nodata] = np.nan
                data[raw == undetect] = np.nan

                data = data * gain + offset

                frames.append(data)

    return frames

@st.cache_data(ttl=3600, show_spinner=False)
def get_extent(file_url):
    response = requests.get(file_url)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".hdf") as tmp:
        tmp.write(response.content)
        tmp.flush()

        with h5py.File(tmp.name, "r") as f:
            where = f["where"].attrs

            return [
                where["LL_lon"],
                where["LR_lon"],
                where["LL_lat"],
                where["UL_lat"]
            ]

def format_time(file_url):
    ts = file_url.split("_")[-1].replace(".hdf", "")
    dt = datetime.strptime(ts, "%Y%m%d%H%M%S")

    return dt.strftime("%d.%m. %H:%M UTC")

@st.cache_data(show_spinner=False)
def load_kraje():
    gdf = gpd.read_file("kraje_wgs84.geojson")
    gdf["geometry"] = gdf.geometry.simplify(0.02, preserve_topology=True)
    return gdf.geometry

kraje = load_kraje()




radar_files = get_latest_radar_files()

base_url = "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/hdf5/"
file_urls = [base_url + f for f in radar_files[::-1]]

extent = get_extent(file_urls[-1])  # any file works, but last is fine

if not radar_files:
    st.error("Nepodařilo se načíst radarová data.")
    st.stop()



frames = load_radar_batch(file_urls)

if "frame_idx" not in st.session_state:
    st.session_state.frame_idx = len(frames) - 1

if "playing" not in st.session_state:
    st.session_state.playing = False


col1, col2 = st.columns(2)

with col1:
    if st.button("▶ Play / Pause"):
        st.session_state.playing = not st.session_state.playing


if st.session_state.playing:
    st.session_state.frame_idx = (st.session_state.frame_idx + 1) % len(frames)
    st.rerun()


frame_idx = st.slider(
    "Radar čas",
    0,
    len(frames) - 1,
    st.session_state.frame_idx
)

st.session_state.frame_idx = frame_idx

#frame_idx = st.slider(
#    "Radar čas",
#    0,
#    len(frames) - 1,
#    len(frames) - 1  # default = newest (important!)
#)




data = frames[frame_idx]

fig = plt.figure(figsize=(10, 6))
ax = plt.axes(projection=ccrs.Mercator())

ax.set_extent([12, 19, 48.3, 51.2], crs=ccrs.PlateCarree())

ax.imshow(
    data,
    origin="lower",
    extent=extent,
    transform=ccrs.PlateCarree(),
    interpolation="nearest"
)

ax.add_feature(cfeature.BORDERS, linewidth=1)
ax.add_feature(cfeature.COASTLINE, linewidth=0.8)

ax.add_geometries(
    kraje,
    crs=ccrs.PlateCarree(),
    edgecolor="black",
    facecolor="none",
    linewidth=0.4
)

ax.set_axis_off()

ax.text(
    0.02, 0.02,
    format_time(file_urls[frame_idx]),
    transform=ax.transAxes,
    fontsize=10,
    color="white",
    bbox=dict(facecolor="black", alpha=0.5, edgecolor="none")
)

st.pyplot(fig)
plt.close(fig)
