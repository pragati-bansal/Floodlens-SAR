import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class SatelliteScene(BaseModel):
    scene_id: str
    satellite: str = "Sentinel-1A"
    sensor_mode: str = "IW"
    product_type: str = "GRD"
    polarizations: List[str] = ["VV", "VH"]
    acquisition_date: str
    orbit_direction: Literal["ASCENDING", "DESCENDING"] = "DESCENDING"
    bbox: List[float] = Field(..., description="[min_lon, min_lat, max_lon, max_lat]")
    region: str
    is_pre_event: bool = False
    source: str = "Copernicus Data Space Ecosystem / Sentinel-1"
    resolution_m: float = 10.0
    orbit_number: Optional[int] = None
    mean_backscatter_db: Optional[float] = None


class ProcessingJobCreate(BaseModel):
    region: str = Field("Delhi NCR", description="Region of Interest name")
    post_event_scene_id: str
    pre_event_scene_id: Optional[str] = None
    polarization: Literal["VV", "VH", "DUAL"] = "VV"
    threshold_db: float = Field(-16.0, description="SAR backscatter water threshold in dB (typically -15 to -18 dB for VV)")
    apply_speckle_filter: bool = True
    exclude_permanent_water: bool = True
    min_polygon_area_sqkm: float = Field(0.005, description="Filter out small noise polygons (in km2)")


class ProcessingJob(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress_pct: int = 0
    region: str
    created_at: str
    completed_at: Optional[str] = None
    post_event_scene_id: str
    pre_event_scene_id: Optional[str] = None
    polarization: str
    threshold_db: float
    total_inundated_area_sqkm: float = 0.0
    polygons_count: int = 0
    affected_roads_count: int = 0
    method: str = "Sentinel-1 SAR Amplitude Thresholding & Change Detection"
    confidence_level: str = "high"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FloodPolygonFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class FloodFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    job_id: Optional[str] = None
    region: Optional[str] = None
    acquisition_date: Optional[str] = None
    features: List[FloodPolygonFeature]
    total_inundated_area_sqkm: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoadRiskAssessment(BaseModel):
    road_id: str
    name: str
    corridor: str
    status: Literal["impassable", "caution", "safe"]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    intersecting_polygon_id: Optional[str] = None
    distance_to_flood_m: float
    flag_reason: str
    evidence_source: Literal["Sentinel-1 SAR", "CCTV Camera", "Citizen Report", "Multi-Source"]
    coordinates: List[List[float]] = Field(..., description="Snapped road line [[lat, lon], ...]")
    assessed_at: str


class CandidateRouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    avoid_sar_floods: bool = True
    max_risk_tolerance: Literal["safe_only", "allow_caution", "unconstrained"] = "safe_only"


class FlaggedSegmentAvoided(BaseModel):
    road_id: str
    name: str
    status: str
    risk_score: float
    flag_reason: str
    flood_evidence: str


class CandidateRouteResponse(BaseModel):
    success: bool
    candidate_type: str = "lower_risk_candidate_route"
    summary: Dict[str, Any]
    coordinates: List[List[float]] = Field(..., description="Route points [[lat, lon], ...]")
    flagged_segments_avoided: List[FlaggedSegmentAvoided]
    safety_disclaimer: str = (
        "Advisory: This is a satellite-derived lower-risk candidate route Skirting radar-detected flood extents. "
        "Ground conditions may change rapidly; passability cannot be unconditionally guaranteed."
    )
    calculated_at: str


class UnifiedObservation(BaseModel):
    id: str
    source_type: Literal["sar_satellite", "camera_edge", "citizen_report"]
    source_id: str
    observation_time: str
    ingestion_time: str
    location_name: str
    latitude: float
    longitude: float
    classification: str
    extent_or_depth: Dict[str, Any]
    confidence: float
    verification_status: str
    evidence_url: Optional[str] = None
