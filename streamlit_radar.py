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

    for url in file_urls:
        response = requests.get(url)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".hdf") as tmp:
            tmp.write(response.content)
            tmp.flush()

            with h5py.File(tmp.name, "r") as f:
                raw = f["dataset1/data1/data"][:]
                attrs = f["dataset1/data1/what"].attrs
                where = f["where"].attrs

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


@st.cache_data(show_spinner=False)
def load_kraje():
    gdf = gpd.read_file("kraje_wgs84.geojson")
    gdf["geometry"] = gdf.geometry.simplify(0.02, preserve_topology=True)
    return gdf.geometry

kraje = load_kraje()


def load_radar_image(file_url):
    response = requests.get(file_url)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".hdf") as tmp:
        tmp.write(response.content)
        tmp.flush()

        with h5py.File(tmp.name, "r") as f:
            raw = f["dataset1/data1/data"][:]
            attrs = f["dataset1/data1/what"].attrs
            where = f["where"].attrs

            gain = attrs["gain"]
            offset = attrs["offset"]
            nodata = attrs["nodata"]
            undetect = attrs["undetect"]

            data = raw.astype(float)
            data[raw == nodata] = np.nan
            data[raw == undetect] = np.nan

            data = data * gain + offset

            extent = [
                where["LL_lon"],
                where["LR_lon"],
                where["LL_lat"],
                where["UL_lat"]
            ]

            return data, extent


radar_files = get_latest_radar_files()

base_url = "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/hdf5/"
file_urls = [base_url + f for f in radar_files]

_, extent = load_radar_image(file_urls[0])

if not radar_files:
    st.error("Nepodařilo se načíst radarová data.")
    st.stop()


selected_file = st.select_slider(
    "Vyber radarový snímek",
    options=radar_files[::-1],
    format_func=lambda x: datetime.strptime(
        x[-18:-4], "%Y%m%d%H%M%S"
    ).strftime("%d.%m. %H:%M"),
    value=radar_files[0]
)



frames = load_radar_batch(file_urls)

frame_idx = st.slider(
    "Radar čas",
    0,
    len(frames) - 1,
    0
)


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

st.pyplot(fig)
plt.close(fig)
