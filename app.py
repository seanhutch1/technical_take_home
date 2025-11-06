import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Parking Analytics", layout="wide")

@st.cache_data # caching decorator for CSV file input
def load_data(path):
    df = pd.read_csv(path)
    df["arrival_time"] = pd.to_datetime(df["arrival_time"], utc=True, errors="coerce")
    # df["departure_time"] = df["arrival_time"] + pd.to_timedelta(df["duration_seconds"], unit="s")
    df["date"] = df["arrival_time"].dt.tz_convert("Australia/Perth").dt.date
    df["hour"] = df["arrival_time"].dt.tz_convert("Australia/Perth").dt.hour
    df["duration_min"] = pd.to_numeric(df["duration_seconds"], errors="coerce") / 60.0
    df["duration_hr"] = df["duration_min"] / 60.0
    return df

def split_valid_invalid(df: pd.DataFrame):
    """Return (accepted, rejected) based on nulls and outliers in latitude and longitude.
    Outliers are flagged using IQR fences per column.
    """
    work = df.copy()

    # Coerce to numeric
    work["latitude"] = pd.to_numeric(work.get("latitude"), errors="coerce")
    work["longitude"] = pd.to_numeric(work.get("longitude"), errors="coerce")

    reasons = []

    # Reason 1 - null coords
    null_mask = work["latitude"].isna() | work["longitude"].isna()
    reasons.append(("NULL_COORDS", null_mask))

    # Reason 1.5 - null plate
    plate_null = work["license_plate"].isna() | (work["license_plate"].astype(str).str.strip() == "")
    reasons.append(("NULL_PLATE", plate_null))


    # Reason 2 - outliers via IQR per column, could use simple static geo fence instead.
    def iqr_fence(s: pd.Series, k: float = 1.5):
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        low, high = q1 - k * iqr, q3 + k * iqr
        return low, high

    lat_low, lat_high = iqr_fence(work["latitude"].dropna(), k=4.5) if work["latitude"].notna().any() else (-90, 90)
    lon_low, lon_high = iqr_fence(work["longitude"].dropna(), k=4.5) if work["longitude"].notna().any() else (-180, 180) # k value for IQR bounds

    lat_out = (work["latitude"] < lat_low) | (work["latitude"] > lat_high)
    lon_out = (work["longitude"] < lon_low) | (work["longitude"] > lon_high)

    reasons.append(("LAT_OUTLIER", lat_out))
    reasons.append(("LON_OUTLIER", lon_out))

    # Combine reasons to a single reject mask and label
    reject_mask = pd.Series(False, index=work.index)
    reject_reason = pd.Series("", index=work.index)

    for label, mask in reasons:
        reject_reason = np.where(mask & ~reject_mask,
                                 np.where(reject_reason == "", label, reject_reason + "," + label),
                                 reject_reason)
        reject_mask = reject_mask | mask

    accepted = work.loc[~reject_mask].copy()
    rejected = work.loc[reject_mask].copy()
    if not rejected.empty:
        rejected["reject_reason"] = reject_reason[reject_mask]

    # Keep fence info for debugging if needed
    meta = {
        "lat_low": float(lat_low) if lat_low is not None else None,
        "lat_high": float(lat_high) if lat_high is not None else None,
        "lon_low": float(lon_low) if lon_low is not None else None,
        "lon_high": float(lon_high) if lon_high is not None else None,
    }
    return accepted, rejected, meta

st.title("Perth Airport Long Term Car Park A")

# Data source
data_src = st.sidebar.radio("Data source", ["Sample data", "Upload CSV"])
if data_src == "Sample data":
    path = "parking-data.csv"
else:
    uploaded = st.sidebar.file_uploader("Upload parking-data.csv", type=["csv"])
    if uploaded is None:
        st.info("Upload a CSV to continue.")
        st.stop()
    path = uploaded

df = load_data(path)

# Filters
st.sidebar.header("Filters")
min_date, max_date = df["arrival_time"].min(), df["arrival_time"].max()
start_date, end_date = st.sidebar.date_input(
    "Date range", value=(min_date.date(), max_date.date())
)
date_mask = (df["arrival_time"].dt.date >= start_date) & (df["arrival_time"].dt.date <= end_date)
filtered_raw = df[date_mask].copy()

# Apply null and outlier handling on filtered data
accepted, rejected, fences = split_valid_invalid(filtered_raw)

# KPIs - use accepted rows
total_stays = int(len(accepted))
unique_plates = int(accepted["license_plate"].nunique())
total_hours = round(accepted["duration_min"].sum() / 60.0, 2)

c1, c2, c3 = st.columns(3)
# c1.metric("Total stays", f"{total_stays}")
c1.metric("Unique vehicles", f"{unique_plates}")
c2.metric("Total occupied hours", f"{total_hours}")
c3.metric("Rejected rows", f"{len(rejected)}")

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Map", "Utilisation by bay", "Time of day", "Durations", "Rejected rows"])

with tab1:
    st.subheader("Bay locations")

    def draw_folium_map(source_df: pd.DataFrame):
        mdf = source_df[["latitude", "longitude", "bay_id", "license_plate", "duration_min"]].dropna()
        if mdf.empty:
            return None
        
        # Compute bounds and fit the view
        lat_min, lat_max = float(mdf["latitude"].min()), float(mdf["latitude"].max())
        lon_min, lon_max = float(mdf["longitude"].min()), float(mdf["longitude"].max())

        center_lat = (lat_min + lat_max) / 2.0
        center_lon = (lon_min + lon_max) / 2.0
        # Start with a neutral map - center/zoom will be set by fit_bounds
        # fmap = folium.Map(tiles="cartodbpositron", control_scale=True)
        fmap = folium.Map(location=[center_lat, center_lon], zoom_start=10, control_scale=True, tiles="cartodbpositron")

        # Add markers
        for _, r in mdf.iterrows():
            parts = []
            if pd.notna(r.get("bay_id", None)):
                parts.append(f"Bay: {r['bay_id']}")
            if pd.notna(r.get("license_plate", None)):
                parts.append(f"Plate: {r['license_plate']}")
            if pd.notna(r.get("duration_min", None)):
                parts.append(f"Stay: {float(r['duration_min']):.1f} min")
            # popup_text = " | ".join(parts) if parts else f"{r['latitude']:.5f}, {r['longitude']:.5f}"
            popup_text = f" {r['bay_id']}\n{r['license_plate']}\nHere for {float(r['duration_min']):.1f} minutes" if parts else f"{r['latitude']:.5f}, {r['longitude']:.5f}"


            folium.CircleMarker(
                location=[float(r["latitude"]), float(r["longitude"])],
                radius=5,
                weight=1,
                fill=True,
                fill_opacity=1,
                popup=popup_text,
            ).add_to(fmap)

        fmap.fit_bounds([[lat_min, lon_min], [lat_max, lon_max]])
        return fmap


    fmap = draw_folium_map(accepted)
    if fmap is None:
        st.info("No valid coordinates to plot.")
    else:

        map_key = f"map_{len(accepted)}_{accepted['latitude'].sum():.6f}_{accepted['longitude'].sum():.6f}" # dynamic key for map zoom problem

        st_folium(fmap, width=None, height=520, returned_objects=[],key=map_key)

    st.caption("Click marker for more information.")
    st.caption("Zoom and Pan enabled.")


with tab2:
    st.subheader("Utilisation by bay")

    if accepted.empty:
        st.info("No data after filtering.")
    else:
        ONE_DAY_MIN = 24 * 60  # 1 day in minutes

        long_df = accepted[accepted["duration_min"] >= ONE_DAY_MIN]
        short_df = accepted[accepted["duration_min"] < ONE_DAY_MIN]

        c1, c2 = st.columns(2)

        # Long-term stays per bay (sum of hours)
        with c1:
            st.markdown("**Long-term stays (≥ 1 day)**")
            if long_df.empty:
                st.caption("No long-term stays in the selected range.")
            else:
                long_by_bay = (
                    long_df.groupby("bay_id")["duration_min"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(20) / 60.0
                )
                fig_long = px.bar(
                    long_by_bay,
                    labels={"value": "Total hours", "bay_id": "Bay"},
                    title=None,
                )
                st.plotly_chart(fig_long, width='content')

        # Short-term stays per bay (sum of hours)
        with c2:
            st.markdown("**Short-term stays (< 1 day)**")
            if short_df.empty:
                st.caption("No short-term stays in the selected range.")
            else:
                short_by_bay = (
                    short_df.groupby("bay_id")["duration_min"]
                    .sum()
                    .sort_values(ascending=False)
                    .head(20) / 60.0
                )
                fig_short = px.bar(
                    short_by_bay,
                    labels={"value": "Total hours", "bay_id": "Bay"},
                    title=None,
                )
                st.plotly_chart(fig_short, width='content')

with tab3:
    st.subheader("Arrivals by hour")
    if accepted.empty:
        st.info("No data after filtering.")
    else:
        arrivals = accepted.groupby("hour").size().reset_index(name="count")
        figa = px.bar(arrivals, x="hour", y="count", labels={"count": "Arrivals"})
        st.plotly_chart(figa, width='content')

        st.subheader("Median stay per hour")
        med = accepted.groupby("hour")["duration_min"].median().reset_index(name="median_min")
        figm = px.line(med, x="hour", y="median_min")
        st.plotly_chart(figm, width='content')

with tab4:
    st.subheader("Stay duration distribution")
    if accepted.empty:
        st.info("No data after filtering.")
    else:
        fig = px.histogram(accepted, x="duration_hr", nbins=100, labels={"duration_hr": "Duration [hr]"})
        st.plotly_chart(fig, width='content')

        st.subheader("Top vehicles by total time")
        v = accepted.groupby("license_plate")["duration_hr"].sum().sort_values(ascending=False).head(20)
        figv = px.bar(v, labels={"value": "Total hours", "license_plate": "Plate"})
        st.plotly_chart(figv, width='content')
        st.dataframe(v.reset_index().rename(columns={"duration_hr": "total_hours"}))

with tab5:
    st.subheader("Rejected rows")
    if rejected.empty:
        st.success("No rejected rows. All coordinates passed validation.")
    else:
        c1, c2 = st.columns(2)
        
        c1.metric("Total rejected", len(rejected))
        c2.caption( f"Latitude bounds: [{fences['lat_low']:.6f}, {fences['lat_high']:.6f}]\n\n " f"Longitude bounds: [{fences['lon_low']:.6f}, {fences['lon_high']:.6f}]" )

        # Show most relevant columns up front
        show_cols = [c for c in ["bay_id", "license_plate", "latitude", "longitude", "arrival_time", "duration_min", "reject_reason"] if c in rejected.columns]
        st.dataframe(rejected[show_cols].reset_index(drop=True), width='content')

        # Optional download of rejected rows
        csv = rejected[show_cols].to_csv(index=False).encode("utf-8")
        st.download_button("Download rejected rows as CSV", data=csv, file_name="rejected_rows.csv", mime="text/csv")

    # Vehicles with multiple entries - computed on the filtered dataset, not just rejected
    st.subheader("Vehicles with multiple entries")
    multi = (
        filtered_raw.groupby("license_plate")
        .agg(
            entries=("license_plate", "size"),
            total_minutes=("duration_min", "sum"),
            first_arrival=("arrival_time", "min"),
            last_arrival=("arrival_time", "max"),
        )
        .reset_index()
    )
    multi = multi[multi["entries"] > 1].copy()

    if multi.empty:
        st.info("No vehicles with multiple entries in the selected date range.")
    else:
        # Convert arrival times to local for display
        multi["first_arrival_local"] = pd.to_datetime(multi["first_arrival"], utc=True).dt.tz_convert("Australia/Perth")
        multi["last_arrival_local"] = pd.to_datetime(multi["last_arrival"], utc=True).dt.tz_convert("Australia/Perth")
        multi["total_hours"] = (multi["total_minutes"] / 60.0).round(2)

        display_cols = [
            "license_plate",
            "entries",
            "total_minutes",
            "total_hours",
            "first_arrival_local",
            "last_arrival_local",
        ]
        multi = multi.sort_values(["entries", "last_arrival"], ascending=[False, False])

        st.dataframe(multi[display_cols], width='content')

        # Optional download
        multi_csv = multi[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download vehicles with multiple entries as CSV",
            data=multi_csv,
            file_name="vehicles_multiple_entries.csv",
            mime="text/csv",
        )

