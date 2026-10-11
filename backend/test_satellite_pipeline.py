"""
FloodLens SAR Satellite & NDRF Road-Risk Test Suite
===================================================
End-to-end integration tests for:
1. Sentinel-1 SAR scene discovery and metadata inspection.
2. SAR amplitude thresholding and change detection processing pipeline.
3. Georeferenced GeoJSON flood polygon generation and validation.
4. Road-risk spatial intersection with LineStrings.
5. Flood-aware lower-risk candidate routing avoiding flooded corridors.
6. Multi-source normalized observations catalog.
"""

import asyncio
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_satellite_scenes_discovery():
    print("\n[TEST 1] Sentinel-1 SAR Scenes Catalog (/api/v1/satellite/scenes)")
    res = client.get("/api/v1/satellite/scenes")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    scenes = res.json()
    assert len(scenes) >= 6, "Expected at least 6 curated scenes"
    print(f"  [OK] Found {len(scenes)} Sentinel-1 scenes in catalog.")

    # Filter by Delhi
    res_delhi = client.get("/api/v1/satellite/scenes?region=Delhi")
    assert res_delhi.status_code == 200
    delhi_scenes = res_delhi.json()
    assert len(delhi_scenes) >= 2, "Expected at least 2 Delhi scenes (pre and post flood)"
    first = delhi_scenes[0]
    assert "S1A_IW_GRDH" in first["scene_id"]
    assert first["sensor_mode"] == "IW"
    assert first["product_type"] == "GRD"
    assert "VV" in first["polarizations"]
    print(f"  [OK] Delhi scene validated: {first['scene_id']} ({first['acquisition_date']})")


def test_sar_processing_job_execution():
    print("\n[TEST 2] SAR Inundation Processing Job Submission & Execution")
    payload = {
        "region": "Delhi NCR",
        "post_event_scene_id": "S1A_IW_GRDH_1SDV_20230713T005322_DELHI_POST",
        "pre_event_scene_id": "S1A_IW_GRDH_1SDV_20230625T005321_DELHI_PRE",
        "polarization": "VV",
        "threshold_db": -16.0,
        "apply_speckle_filter": True,
        "exclude_permanent_water": True,
        "min_polygon_area_sqkm": 0.005,
    }
    res = client.post("/api/v1/satellite/processing-jobs", json=payload)
    assert res.status_code == 202, f"Expected 202 Accepted, got {res.status_code}"
    job = res.json()
    job_id = job["job_id"]
    print(f"  [OK] Processing job submitted with ID: {job_id}")

    # Wait briefly for background execution
    import time
    for _ in range(10):
        time.sleep(0.5)
        res_status = client.get(f"/api/v1/satellite/processing-jobs/{job_id}")
        if res_status.status_code == 200:
            current_job = res_status.json()
            if current_job["status"] == "completed":
                print(f"  [OK] Job completed successfully!")
                print(f"    - Inundated Area: {current_job['total_inundated_area_sqkm']} km²")
                print(f"    - Polygons Detected: {current_job['polygons_count']}")
                print(f"    - Affected Corridors: {current_job['affected_roads_count']}")
                assert current_job["polygons_count"] > 0
                return job_id
    raise TimeoutError(f"Job {job_id} did not finish within timeout.")


def test_flood_polygons_geojson():
    print("\n[TEST 3] Georeferenced Flood Polygons (/api/v1/flood/polygons)")
    res = client.get("/api/v1/flood/polygons")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    features = data["features"]
    assert len(features) > 0, "Expected non-empty flood polygon features"
    f0 = features[0]
    assert f0["type"] == "Feature"
    assert f0["geometry"]["type"] in ("Polygon", "MultiPolygon")
    props = f0["properties"]
    assert "polygon_id" in props
    assert props["area_sqkm"] > 0
    assert "mean_backscatter_db" in props
    assert props["source"] == "Sentinel-1 SAR (C-band IW GRDH)"
    print(f"  [OK] Successfully retrieved {len(features)} valid GeoJSON flood polygons.")
    print(f"    - Sample Polygon: {props['polygon_id']} ({props['area_sqkm']} km², {props['mean_backscatter_db']} dB)")


def test_road_risk_evaluations():
    print("\n[TEST 4] Road-Risk Spatial Intersections (/api/v1/roads/risks)")
    res = client.get("/api/v1/roads/risks")
    assert res.status_code == 200
    risks = res.json()
    assert len(risks) >= 10, "Expected at least 10 monitored arterial road corridors"
    
    impassable = [r for r in risks if r["status"] == "impassable"]
    caution = [r for r in risks if r["status"] == "caution"]
    safe = [r for r in risks if r["status"] == "safe"]

    print(f"  [OK] Evaluated {len(risks)} corridors:")
    print(f"    - Impassable: {len(impassable)} ({[r['name'] for r in impassable[:3]]}...)")
    print(f"    - Caution:    {len(caution)} ({[r['name'] for r in caution[:3]]}...)")
    print(f"    - Safe:       {len(safe)} ({[r['name'] for r in safe[:3]]}...)")

    assert len(impassable) > 0, "Expected flooded corridors (e.g., Minto Bridge, ITO)"
    assert any("Minto Bridge" in r["name"] for r in impassable)
    assert any("ITO" in r["name"] for r in impassable)


def test_flood_aware_candidate_routing():
    print("\n[TEST 5] Flood-Aware Lower-Risk Candidate Routing (/api/v1/routes/calculate)")
    # Route from CP to AIIMS
    payload = {
        "origin_lat": 28.6315,
        "origin_lon": 77.2167,
        "destination_lat": 28.5684,
        "destination_lon": 77.2088,
        "avoid_sar_floods": True,
        "max_risk_tolerance": "safe_only",
    }
    res = client.post("/api/v1/routes/calculate", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    route = res.json()
    assert route["success"] is True
    assert route["candidate_type"] == "lower_risk_candidate_route"
    assert len(route["coordinates"]) > 10
    assert len(route["flagged_segments_avoided"]) > 0
    print(f"  [OK] Calculated candidate route:")
    print(f"    - Distance: {route['summary']['total_distance_km']} km")
    print(f"    - Duration: {route['summary']['estimated_duration_min']} mins")
    print(f"    - Safety Rating: {route['summary']['safety_rating']}")
    print(f"    - Snapped Waypoints: {len(route['coordinates'])}")
    print(f"    - Avoided Flooded Corridors: {len(route['flagged_segments_avoided'])}")
    print(f"    - Disclaimer: {route['safety_disclaimer'][:60]}...")


def test_unified_observations():
    print("\n[TEST 6] Normalized Multi-Source Observations (/api/v1/flood/observations)")
    res = client.get("/api/v1/flood/observations")
    assert res.status_code == 200
    obs = res.json()
    assert len(obs) > 0
    sources = set(o["source_type"] for o in obs)
    assert "sar_satellite" in sources
    assert "camera_edge" in sources
    assert "citizen_report" in sources
    print(f"  [OK] Successfully retrieved {len(obs)} unified observations across sources: {sorted(list(sources))}")


if __name__ == "__main__":
    print("=" * 65)
    print(">> Starting FloodLens SAR Satellite & NDRF Test Suite")
    print("=" * 65)
    test_satellite_scenes_discovery()
    test_sar_processing_job_execution()
    test_flood_polygons_geojson()
    test_road_risk_evaluations()
    test_flood_aware_candidate_routing()
    test_unified_observations()
    print("\n" + "=" * 65)
    print(">> ALL SAR PIPELINE & NDRF TESTS PASSED PERFECTLY!")
    print("=" * 65)
