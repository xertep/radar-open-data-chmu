import requests
import re
from datetime import datetime, timedelta
import h5py
import tempfile


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


radar_files = get_latest_radar_files()

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


file_url = (
    "https://opendata.chmi.cz/meteorology/weather/radar/composite/maxz/hdf5/"
    + selected_file
)

st.write(file_url)
