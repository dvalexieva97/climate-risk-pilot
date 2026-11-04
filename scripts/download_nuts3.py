#!/usr/bin/env python3
"""Download NUTS3 boundaries for a country from Eurostat GISCO."""

from __future__ import annotations

import argparse
import zipfile
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import requests

# Eurostat GISCO 2021 1:3M NUTS3
NUTS_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
    "NUTS_RG_01M_2021_4326_LEVL_3.geojson"
)

COUNTRY_NUTS0 = {
    "portugal": "PT",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NUTS3 GeoJSON for pilot region")
    parser.add_argument("--country", default="portugal", choices=COUNTRY_NUTS0.keys())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reference/nuts3_portugal.geojson"),
    )
    args = parser.parse_args()
    code = COUNTRY_NUTS0[args.country]

    print(f"Fetching NUTS3 from Eurostat GISCO...")
    response = requests.get(NUTS_URL, timeout=180)
    response.raise_for_status()
    gdf = gpd.read_file(BytesIO(response.content))
    country = gdf[gdf["CNTR_CODE"] == code].copy()
    if country.empty:
        raise SystemExit(f"No NUTS3 features for {code}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    country = country[["NUTS_ID", "NAME_LATN", "geometry"]]
    country.to_file(args.output, driver="GeoJSON")
    print(f"Saved {len(country)} NUTS3 units to {args.output}")


if __name__ == "__main__":
    main()
