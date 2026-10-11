"""
FloodLens Road-Risk Assessment and NDRF Flood-Aware Candidate Routing
======================================================================
Connects Sentinel-1 SAR flood inundation polygons with urban road corridors.
Computes:
1. Spatial intersection between road LineStrings and flood Polygons using Shapely.
2. Buffer proximity risk scores (Impassable: direct intersect, Caution: <300m, Safe: clear).
3. Dynamic Dijkstra pathfinding excluding inundated corridors.
4. OSRM road geometry snapping for realistic commuter & NDRF emergency deployment.
5. Explainable route transparency (avoided flooded segments, warning flags, disclaimer).
"""

import datetime
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import httpx
import networkx as nx
from shapely.geometry import LineString, Point, shape

from ..core.config import settings
from ..schemas.satellite import (
    CandidateRouteResponse,
    FlaggedSegmentAvoided,
    RoadRiskAssessment,
)

logger = logging.getLogger("floodlens.road_risk")

# Key Delhi arterial and rescue corridors with realistic coordinates
DELHI_CORRIDORS: List[Dict[str, Any]] = [
    {
        "road_id": "ROAD-01",
        "name": "Minto Bridge Railway Underpass (DDU Marg)",
        "corridor": "Central Delhi Transit Link",
        "node_a": "CONN_PLACE",
        "node_b": "ITO_CROSS",
        "coordinates": [
            [28.6328, 77.2195],
            [28.6325, 77.2215],
            [28.6320, 77.2240],
            [28.6305, 77.2350],
            [28.6297, 77.2425],
        ],
    },
    {
        "road_id": "ROAD-02",
        "name": "ITO Crossing - Vikas Marg (Yamuna Bridge)",
        "corridor": "East-Central River Crossing",
        "node_a": "ITO_CROSS",
        "node_b": "LAXMI_NAGAR",
        "coordinates": [
            [28.6297, 77.2425],
            [28.6295, 77.2510],
            [28.6288, 77.2600],
            [28.6275, 77.2750],
        ],
    },
    {
        "road_id": "ROAD-03",
        "name": "Kashmere Gate ISBT - Monastery Market (Ring Road North)",
        "corridor": "North Yamuna Embankment",
        "node_a": "KASHMERE_GATE",
        "node_b": "DELHI_GATE",
        "coordinates": [
            [28.6675, 77.2280],
            [28.6650, 77.2330],
            [28.6550, 77.2390],
            [28.6420, 77.2410],
            [28.6350, 77.2420],
        ],
    },
    {
        "road_id": "ROAD-04",
        "name": "Pul Prahladpur Underpass (Mehrauli-Badarpur Rd)",
        "corridor": "South Delhi Arterial",
        "node_a": "MOOLCHAND",
        "node_b": "BADARPUR",
        "coordinates": [
            [28.5672, 77.2340],
            [28.5350, 77.2600],
            [28.5120, 77.2750],
            [28.4980, 77.2882],
            [28.4920, 77.2990],
        ],
    },
    {
        "road_id": "ROAD-05",
        "name": "Zakhira Underpass (Rohtak Road - Patel Nagar)",
        "corridor": "West Delhi Bypass",
        "node_a": "ZAKHIRA",
        "node_b": "CONN_PLACE",
        "coordinates": [
            [28.6720, 77.1585],
            [28.6550, 77.1750],
            [28.6450, 77.1950],
            [28.6315, 77.2167],
        ],
    },
    {
        "road_id": "ROAD-06",
        "name": "Barapullah Elevated Corridor (AIIMS to Sarai Kale Khan)",
        "corridor": "Elevated Expressway (Flood-Bypass)",
        "node_a": "AIIMS",
        "node_b": "SARAI_KALE_KHAN",
        "coordinates": [
            [28.5684, 77.2088],
            [28.5720, 77.2250],
            [28.5810, 77.2450],
            [28.5890, 77.2560],
        ],
    },
    {
        "road_id": "ROAD-07",
        "name": "Shanti Path - Sardar Patel Marg (Dhaula Kuan to CP)",
        "corridor": "Diplomatic Ridge Corridor (High Elevation)",
        "node_a": "DHAULA_KUAN",
        "node_b": "CONN_PLACE",
        "coordinates": [
            [28.5921, 77.1616],
            [28.6010, 77.1800],
            [28.6150, 77.1980],
            [28.6315, 77.2167],
        ],
    },
    {
        "road_id": "ROAD-08",
        "name": "Ring Road South (Dhaula Kuan to AIIMS)",
        "corridor": "South Arterial Corridor",
        "node_a": "DHAULA_KUAN",
        "node_b": "AIIMS",
        "coordinates": [
            [28.5921, 77.1616],
            [28.5800, 77.1750],
            [28.5710, 77.1920],
            [28.5684, 77.2088],
        ],
    },
    {
        "road_id": "ROAD-09",
        "name": "Aurobindo Marg (Connaught Place to AIIMS)",
        "corridor": "Central to South Arterial Spine",
        "node_a": "CONN_PLACE",
        "node_b": "AIIMS",
        "coordinates": [
            [28.6315, 77.2167],
            [28.6100, 77.2140],
            [28.5900, 77.2110],
            [28.5684, 77.2088],
        ],
    },
    {
        "road_id": "ROAD-10",
        "name": "Ring Road South-East (AIIMS to Moolchand)",
        "corridor": "Ring Road South Segment",
        "node_a": "AIIMS",
        "node_b": "MOOLCHAND",
        "coordinates": [
            [28.5684, 77.2088],
            [28.5678, 77.2210],
            [28.5672, 77.2340],
        ],
    },
    {
        "road_id": "ROAD-11",
        "name": "Ring Road West (Zakhira to Dhaula Kuan)",
        "corridor": "West Arterial Spine",
        "node_a": "ZAKHIRA",
        "node_b": "DHAULA_KUAN",
        "coordinates": [
            [28.6720, 77.1585],
            [28.6400, 77.1550],
            [28.6100, 77.1580],
            [28.5921, 77.1616],
        ],
    },
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance in kilometers."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class RoadRiskService:
    """Evaluates road-network flood risk and calculates lower-risk candidate routes."""

    def __init__(self):
        self._corridors = DELHI_CORRIDORS
        self._http_client = httpx.AsyncClient(timeout=8.0)

    def evaluate_road_risks(
        self, flood_features: List[Dict[str, Any]]
    ) -> List[RoadRiskAssessment]:
        """
        Intersects road corridor LineStrings with Sentinel-1 SAR flood Polygons.
        Classifies risk:
        - impassable: road directly intersects flood polygon (risk: 0.95)
        - caution: road within 300m buffer of flood polygon (risk: 0.60)
        - safe: clear of detected floodwaters (risk: 0.05)
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        poly_geoms = []

        for feat in flood_features:
            geom = feat.get("geometry", {})
            try:
                poly = shape(geom)
                if poly.is_valid and not poly.is_empty:
                    poly_geoms.append((poly, feat.get("properties", {})))
            except Exception as e:
                logger.warning(f"Failed to parse flood polygon: {e}")

        assessments: List[RoadRiskAssessment] = []

        for road in self._corridors:
            # Construct road LineString (WGS84 lon, lat for Shapely)
            coords_lonlat = [[pt[1], pt[0]] for pt in road["coordinates"]]
            road_line = LineString(coords_lonlat)

            status = "safe"
            risk_score = 0.05
            intersecting_poly_id = None
            min_dist_m = 99999.0
            flag_reason = "Corridor clear of radar-detected floodwaters"

            for poly, props in poly_geoms:
                p_id = props.get("polygon_id", "SAR-POLY")
                if poly.intersects(road_line):
                    status = "impassable"
                    risk_score = 0.95
                    intersecting_poly_id = p_id
                    min_dist_m = 0.0
                    flag_reason = f"Directly intersects Sentinel-1 SAR flood polygon ({p_id})"
                    break  # Highest severity reached

                # Check proximity buffer
                dist_deg = poly.distance(road_line)
                dist_m = dist_deg * 111320.0  # Approx at Delhi latitude
                if dist_m < min_dist_m:
                    min_dist_m = dist_m

                if dist_m < 300.0 and status != "impassable":
                    status = "caution"
                    risk_score = 0.60
                    intersecting_poly_id = p_id
                    flag_reason = f"Located within {int(dist_m)}m proximity buffer of flood polygon ({p_id})"

            assessment = RoadRiskAssessment(
                road_id=road["road_id"],
                name=road["name"],
                corridor=road["corridor"],
                status=status,
                risk_score=risk_score,
                intersecting_polygon_id=intersecting_poly_id,
                distance_to_flood_m=round(min_dist_m, 1) if min_dist_m < 99999.0 else 2500.0,
                flag_reason=flag_reason,
                evidence_source="Sentinel-1 SAR",
                coordinates=road["coordinates"],
                assessed_at=now_iso,
            )
            assessments.append(assessment)

        return assessments

    async def calculate_lower_risk_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        road_risks: List[RoadRiskAssessment],
        avoid_sar_floods: bool = True,
        max_risk_tolerance: str = "safe_only",
    ) -> CandidateRouteResponse:
        """
        Calculates lower-risk candidate route using NetworkX graph with dynamic flood penalties.
        Snaps waypoints to OpenStreetMap road geometry via OSRM.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Build risk lookup by road_id
        risk_map = {r.road_id: r for r in road_risks}

        # Build NetworkX undirected graph of corridor nodes
        g = nx.Graph()
        nodes = set()

        for c in self._corridors:
            u, v = c["node_a"], c["node_b"]
            nodes.add(u)
            nodes.add(v)
            r_info = risk_map.get(c["road_id"])
            status = r_info.status if r_info else "safe"

            # Compute corridor physical length
            coords = c["coordinates"]
            length_km = 0.0
            for i in range(len(coords) - 1):
                length_km += haversine_km(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])

            # Apply dynamic hazard penalties
            if avoid_sar_floods and status == "impassable":
                weight = 1_000_000.0  # Heavily pruned
            elif status == "caution":
                weight = length_km * (1.5 if max_risk_tolerance == "allow_caution" else 4.0)
            else:
                weight = length_km

            g.add_edge(u, v, weight=weight, length_km=length_km, road_id=c["road_id"], status=status)

        # Resolve nearest corridor nodes to origin and destination
        def find_nearest_node(lat: float, lon: float) -> str:
            best_node = None
            best_dist = float("inf")
            for c in self._corridors:
                first_pt = c["coordinates"][0]
                last_pt = c["coordinates"][-1]
                d1 = haversine_km(lat, lon, first_pt[0], first_pt[1])
                d2 = haversine_km(lat, lon, last_pt[0], last_pt[1])
                if d1 < best_dist:
                    best_dist = d1
                    best_node = c["node_a"]
                if d2 < best_dist:
                    best_dist = d2
                    best_node = c["node_b"]
            return best_node or "CONN_PLACE"

        orig_node = find_nearest_node(origin_lat, origin_lon)
        dest_node = find_nearest_node(dest_lat, dest_lon)

        flagged_avoided: List[FlaggedSegmentAvoided] = []
        impassable_roads = [r for r in road_risks if r.status == "impassable"]

        for imp in impassable_roads:
            flagged_avoided.append(
                FlaggedSegmentAvoided(
                    road_id=imp.road_id,
                    name=imp.name,
                    status=imp.status,
                    risk_score=imp.risk_score,
                    flag_reason=imp.flag_reason,
                    flood_evidence=imp.evidence_source,
                )
            )

        # Calculate path
        path_nodes = []
        path_edges = []
        try:
            path_nodes = nx.shortest_path(g, source=orig_node, target=dest_node, weight="weight")
            for i in range(len(path_nodes) - 1):
                edge_data = g.get_edge_data(path_nodes[i], path_nodes[i+1])
                path_edges.append(edge_data)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            logger.warning(f"No fully safe path between {orig_node} and {dest_node}. Falling back to unconstrained shortest physical path.")
            try:
                path_nodes = nx.shortest_path(g, source=orig_node, target=dest_node, weight="length_km")
                for i in range(len(path_nodes) - 1):
                    edge_data = g.get_edge_data(path_nodes[i], path_nodes[i+1])
                    path_edges.append(edge_data)
            except Exception as e:
                logger.error(f"Routing failed completely: {e}")

        # Assemble waypoints
        waypoints: List[List[float]] = [[origin_lat, origin_lon]]
        for edge in path_edges:
            r_id = edge.get("road_id")
            match_corridor = next((c for c in self._corridors if c["road_id"] == r_id), None)
            if match_corridor:
                for pt in match_corridor["coordinates"]:
                    if pt not in waypoints:
                        waypoints.append(pt)
        waypoints.append([dest_lat, dest_lon])

        # Attempt OSRM snapping for real road geometry
        snapped_coords: List[List[float]] = waypoints
        total_dist_km = 0.0
        est_duration_min = 0.0

        try:
            # Query OSRM
            wp_str = ";".join([f"{pt[1]:.6f},{pt[0]:.6f}" for pt in waypoints[:8]])
            osrm_url = f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{wp_str}?overview=full&geometries=geojson"
            resp = await self._http_client.get(osrm_url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("routes") and len(data["routes"]) > 0:
                    route0 = data["routes"][0]
                    # Convert OSRM [lon, lat] to [lat, lon]
                    snapped_coords = [[c[1], c[0]] for c in route0["geometry"]["coordinates"]]
                    total_dist_km = round(route0["distance"] / 1000.0, 2)
                    est_duration_min = round(route0["duration"] / 60.0, 1)
        except Exception as e:
            logger.warning(f"OSRM snapping failed, using geometric waypoints: {e}")

        if total_dist_km == 0.0:
            # Calculate geometric distance fallback
            for i in range(len(snapped_coords) - 1):
                total_dist_km += haversine_km(
                    snapped_coords[i][0], snapped_coords[i][1],
                    snapped_coords[i+1][0], snapped_coords[i+1][1]
                )
            total_dist_km = round(total_dist_km, 2)
            est_duration_min = round((total_dist_km / 35.0) * 60.0, 1)

        # Determine overall safety rating
        route_statuses = [e.get("status") for e in path_edges]
        if "impassable" in route_statuses:
            safety_rating = "impassable"
        elif "caution" in route_statuses:
            safety_rating = "caution_advisory"
        else:
            safety_rating = "safe"

        return CandidateRouteResponse(
            success=True,
            candidate_type="lower_risk_candidate_route",
            summary={
                "total_distance_km": total_dist_km,
                "estimated_duration_min": est_duration_min,
                "safety_rating": safety_rating,
                "waypoints_count": len(snapped_coords),
                "nodes_traversed": path_nodes,
                "avoided_flooded_corridors_count": len(flagged_avoided),
            },
            coordinates=snapped_coords,
            flagged_segments_avoided=flagged_avoided,
            safety_disclaimer=(
                "Advisory: This is a satellite-derived lower-risk candidate route skirting radar-detected flood extents. "
                "Ground conditions may change rapidly; passability cannot be unconditionally guaranteed."
            ),
            calculated_at=now_iso,
        )


road_risk_service = RoadRiskService()
