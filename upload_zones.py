import geopandas as gpd
import mysql.connector
import os
import json

# ✅ Connect to MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="DmKjayeshmysql@155",
    database="quotivate_db"
)
cursor = conn.cursor()

# ✅ Map cities to their states manually
CITY_STATE_MAP = {
    "Pune": "Maharashtra",
    "Bangalore": "Karnataka"
}

# ✅ Folder where GeoJSON files for all cities are stored
CITIES_FOLDER = "cities"

# ✅ Loop through each GeoJSON file in the folder
for filename in os.listdir(CITIES_FOLDER):
    if filename.endswith(".geojson"):
        file_path = os.path.join(CITIES_FOLDER, filename)

        # ✅ Extract city name
        city_name = filename.replace("_zones.geojson", "").replace(".geojson", "").capitalize()

        print(f"\n📍 Processing zones for city: {city_name}")

        # ✅ Get state name
        state_name = CITY_STATE_MAP.get(city_name)
        if not state_name:
            print(f"⚠️ No state mapped for city '{city_name}', skipping...")
            continue

        # ✅ Insert or get state_id from `states` table
        cursor.execute("INSERT IGNORE INTO states (state_name) VALUES (%s)", (state_name,))
        conn.commit()

        cursor.execute("SELECT state_id FROM states WHERE state_name = %s", (state_name,))
        result = cursor.fetchone()
        if not result:
            print(f"⚠️ Failed to retrieve state_id for {state_name}, skipping...")
            continue
        state_id = result[0]

        # ✅ Insert city and state_id (update if city already exists)
        cursor.execute("""
            INSERT INTO cities (city_name, state_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE state_id = VALUES(state_id)
        """, (city_name, state_id))
        conn.commit()

        # ✅ Get city_id
        cursor.execute("SELECT city_id FROM cities WHERE city_name = %s", (city_name,))
        result = cursor.fetchone()
        if not result:
            print(f"⚠️ Failed to retrieve city_id for {city_name}, skipping...")
            continue
        city_id = result[0]

        # ✅ Load the GeoJSON
        gdf = gpd.read_file(file_path)
        zone_count = 0

        for _, row in gdf.iterrows():
            zone_name = (
                row.get('Name2') or
                row.get('Name1') or
                row.get('name') or
                row.get('WARD_NAME') or
                row.get('ward_name') or
                row.get('zone_name') or
                (f"Ward {row.get('wardnum')}" if row.get('wardnum') else None) or
                "Unnamed Zone"
            )

            print(f"🧩 Zone Name: {zone_name} | Available fields: {list(row.keys())}")
            geometry = row['geometry']

            if geometry is None or geometry.is_empty:
                print(f"⛔ Skipping zone '{zone_name}' due to empty geometry.")
                continue

            if not geometry.is_valid:
                print(f"⛔ Skipping zone '{zone_name}' due to invalid geometry.")
                continue

            try:
                centroid = geometry.centroid
                lat, lng = centroid.y, centroid.x

                wkt_polygon = geometry.wkt
                geojson_shape = json.dumps(
                    json.loads(gpd.GeoSeries([geometry]).to_json())["features"][0]["geometry"]
                )

                cursor.execute("""
                    INSERT INTO zones (zone_name, latitude, longitude, boundary_polygon, boundary_geojson, city_id)
                    VALUES (%s, %s, %s, ST_GeomFromText(%s), %s, %s)
                """, (zone_name, lat, lng, wkt_polygon, geojson_shape, city_id))

                zone_count += 1

            except mysql.connector.errors.IntegrityError:
                print(f"⚠️ Duplicate zone name '{zone_name}', skipping...")
                continue

            except mysql.connector.errors.DataError as db_err:
                print(f"🚫 MySQL rejected zone '{zone_name}' due to invalid GIS data.")
                print(f"    ↪️ Skipping... Reason: {db_err}")
                continue

            except Exception as e:
                print(f"⚠️ Unexpected error while inserting zone '{zone_name}': {e}")
                continue

        print(f"✅ Finished uploading {zone_count} zones for {city_name}")

# ✅ Finalize
conn.commit()
cursor.close()
conn.close()

print("\n🎉 All city zones uploaded successfully!")
