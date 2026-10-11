"""
FloodLens API - Satellite SAR Inundation Mapping & Road-Risk Endpoints
======================================================================
Provides REST endpoints for:
1. Sentinel-1 SAR scene discovery and metadata inspection.
2. Background SAR flood processing jobs.
3. Georeferenced flood inundation GeoJSON polygons.
4. Road-risk spatial assessments.
5. Flood-aware lower-risk candidate routing for NDRF operations.
6. Unified multi-source observation catalog (SAR, Camera, Citizen).
"""

import asyncio
import datetime
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from ..core.database import db
from ..schemas.satellite import (
    CandidateRouteRequest,
    CandidateRouteResponse,
    FloodFeatureCollection,
    FloodPolygonFeature,
    ProcessingJob,
    ProcessingJobCreate,
    RoadRiskAssessment,
    SatelliteScene,
    UnifiedObservation,
)
from ..services.road_risk_service import road_risk_service
from ..services.sar_service import sar_service

logger = logging.getLogger("floodlens.api.satellite")

router = APIRouter(tags=["Satellite & NDRF Flood Intelligence"])


# 1. Satellite Scenes Catalog
@router.get("/satellite/scenes", response_model=List[SatelliteScene])
async def list_satellite_scenes(
    region: Optional[str] = Query(None, description="Filter scenes by region name (e.g. 'Delhi NCR', 'Assam', 'Bihar')")
):
    """
    Retrieves catalog of available Sentinel-1 IW GRDH SAR acquisitions with metadata.
    Includes orbit directions, polarization modes (VV/VH), resolution, and bounding boxes.
    """
    scenes = sar_service.get_scenes(region=region)
    return scenes


# 2. Asynchronous Job Runner
async def _run_sar_processing_task(job_id: str, payload: ProcessingJobCreate):
    """Background task to execute SAR pipeline and persist results."""
    try:
        # Mark as processing
        await db.save_processing_job({
            "job_id": job_id,
            "status": "processing",
            "progress_pct": 35,
            "region": payload.region,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "post_event_scene_id": payload.post_event_scene_id,
            "pre_event_scene_id": payload.pre_event_scene_id,
            "polarization": payload.polarization,
            "threshold_db": payload.threshold_db,
            "total_inundated_area_sqkm": 0.0,
            "polygons_count": 0,
            "affected_roads_count": 0,
            "method": "Executing Sentinel-1 SAR Preprocessing & Amplitude Thresholding...",
            "confidence_level": "high",
            "metadata": {},
        })

        # Run SAR processing pipeline
        job_result, fc = await sar_service.execute_flood_inundation_job(payload, job_id=job_id)

        # Evaluate road risk intersections
        features_dict = [f.model_dump() for f in fc.features]
        road_risks = road_risk_service.evaluate_road_risks(features_dict)
        affected_count = len([r for r in road_risks if r.status in ("impassable", "caution")])

        # Update job with affected roads count
        job_result.affected_roads_count = affected_count

        # Persist to database
        await db.save_processing_job(job_result.model_dump())
        await db.save_flood_polygons(job_id, [f.model_dump() for f in fc.features])
        await db.save_road_risks([r.model_dump() for r in road_risks])

        logger.info(f"SAR processing job {job_id} completed successfully. Polygons: {len(fc.features)}, Affected roads: {affected_count}")
    except Exception as e:
        logger.error(f"SAR processing job {job_id} failed: {e}")
        await db.save_processing_job({
            "job_id": job_id,
            "status": "failed",
            "progress_pct": 0,
            "region": payload.region,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "post_event_scene_id": payload.post_event_scene_id,
            "pre_event_scene_id": payload.pre_event_scene_id,
            "polarization": payload.polarization,
            "threshold_db": payload.threshold_db,
            "total_inundated_area_sqkm": 0.0,
            "polygons_count": 0,
            "affected_roads_count": 0,
            "method": "Pipeline execution aborted",
            "confidence_level": "low",
            "error_message": str(e),
            "metadata": {},
        })


@router.post("/satellite/processing-jobs", response_model=ProcessingJob, status_code=status.HTTP_202_ACCEPTED)
async def create_processing_job(
    payload: ProcessingJobCreate,
    background_tasks: BackgroundTasks,
):
    """
    Submits a Sentinel-1 SAR flood inundation processing job.
    Processes SAR amplitude, applies speckle filter, executes change detection,
    generates GeoJSON flood polygons, and evaluates road intersections.
    """
    import uuid
    job_id = f"job-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    initial_job = {
        "job_id": job_id,
        "status": "queued",
        "progress_pct": 5,
        "region": payload.region,
        "created_at": now_iso,
        "post_event_scene_id": payload.post_event_scene_id,
        "pre_event_scene_id": payload.pre_event_scene_id,
        "polarization": payload.polarization,
        "threshold_db": payload.threshold_db,
        "total_inundated_area_sqkm": 0.0,
        "polygons_count": 0,
        "affected_roads_count": 0,
        "method": "Queued Sentinel-1 SAR Calibration Pipeline",
        "confidence_level": "high",
        "metadata": {},
    }
    await db.save_processing_job(initial_job)

    # Immediately execute processing or schedule in background
    background_tasks.add_task(_run_sar_processing_task, job_id, payload)

    return ProcessingJob(**initial_job)


@router.get("/satellite/processing-jobs", response_model=List[ProcessingJob])
async def list_processing_jobs():
    """Lists all historical and active SAR processing jobs."""
    jobs = await db.get_processing_jobs()
    return [ProcessingJob(**j) for j in jobs]


@router.get("/satellite/processing-jobs/{job_id}", response_model=ProcessingJob)
async def get_processing_job_status(job_id: str):
    """Fetches real-time status and telemetry metrics for a specific processing job."""
    job = await db.get_processing_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processing job '{job_id}' not found."
        )
    return ProcessingJob(**job)


# 3. Flood Polygons GeoJSON Feed
@router.get("/flood/polygons", response_model=FloodFeatureCollection)
async def get_flood_polygons(
    job_id: Optional[str] = Query(None, description="Optional job ID to fetch specific polygons"),
    region: Optional[str] = Query(None, description="Optional region filter (e.g. 'Delhi NCR')"),
):
    """
    Returns georeferenced flood inundation polygons in GeoJSON format.
    If no job_id is specified and no jobs exist, automatically initializes baseline polygons for Delhi.
    """
    polygons = await db.get_flood_polygons(job_id=job_id)

    # If no polygons in database yet, auto-generate baseline for Delhi demonstration
    if not polygons:
        default_req = ProcessingJobCreate(
            region=region or "Delhi NCR",
            post_event_scene_id="S1A_IW_GRDH_1SDV_20230713T005322_DELHI_POST",
            pre_event_scene_id="S1A_IW_GRDH_1SDV_20230625T005321_DELHI_PRE",
        )
        j_id = "job-delhi-baseline"
        job_result, fc = await sar_service.execute_flood_inundation_job(default_req, job_id=j_id)
        
        # Evaluate road intersections
        features_dict = [f.model_dump() for f in fc.features]
        road_risks = road_risk_service.evaluate_road_risks(features_dict)
        affected_count = len([r for r in road_risks if r.status in ("impassable", "caution")])
        job_result.affected_roads_count = affected_count

        await db.save_processing_job(job_result.model_dump())
        await db.save_flood_polygons(j_id, features_dict)
        await db.save_road_risks([r.model_dump() for r in road_risks])

        return fc

    features = [FloodPolygonFeature(**p) for p in polygons]
    total_area = sum(f.properties.get("area_sqkm", 0.0) for f in features)

    return FloodFeatureCollection(
        type="FeatureCollection",
        job_id=job_id or "latest",
        region=region or "Delhi NCR",
        features=features,
        total_inundated_area_sqkm=round(total_area, 4),
        metadata={
            "source": "Sentinel-1 SAR C-band IW GRDH",
            "polygons_count": len(features),
        },
    )


# 4. Road Risk Assessments
@router.get("/roads/risks", response_model=List[RoadRiskAssessment])
async def get_road_risks():
    """
    Returns current risk assessments for monitored urban road corridors,
    including impassable sections intersecting SAR flood extent and safe bypass routes.
    """
    risks = await db.get_road_risks()
    if not risks:
        # Evaluate against active polygons
        fc = await get_flood_polygons()
        features_dict = [f.model_dump() for f in fc.features]
        evaluated = road_risk_service.evaluate_road_risks(features_dict)
        await db.save_road_risks([r.model_dump() for r in evaluated])
        return evaluated
    return [RoadRiskAssessment(**r) for r in risks]


# 5. Flood-Aware Candidate Routing
@router.post("/routes/calculate", response_model=CandidateRouteResponse)
async def calculate_candidate_route(payload: CandidateRouteRequest):
    """
    Calculates a lower-risk candidate route between origin and destination coordinates,
    dynamically pruning or penalizing road corridors intersecting radar-detected floodwaters.
    """
    try:
        risks = await get_road_risks()
        result = await road_risk_service.calculate_lower_risk_route(
            origin_lat=payload.origin_lat,
            origin_lon=payload.origin_lon,
            dest_lat=payload.destination_lat,
            dest_lon=payload.destination_lon,
            road_risks=risks,
            avoid_sar_floods=payload.avoid_sar_floods,
            max_risk_tolerance=payload.max_risk_tolerance,
        )
        return result
    except Exception as e:
        logger.error(f"Candidate route calculation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Route calculation failed: {str(e)}"
        )


# 6. Unified Multi-Source Observations
@router.get("/flood/observations", response_model=List[UnifiedObservation])
async def get_unified_observations():
    """
    Returns normalized flood observations across:
    1. Sentinel-1 SAR satellite inundation footprints.
    2. Ground CCTV camera telemetry stations.
    3. Citizen crowdsourced reports with 500m proximity verification.
    Keeps satellite inundation separate from depth measurements with transparent provenance.
    """
    observations: List[UnifiedObservation] = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. SAR Satellite Polygons
    polys = await db.get_flood_polygons()
    for idx, p in enumerate(polys[:10]):
        props = p.get("properties", {})
        geom = p.get("geometry", {})
        coords = geom.get("coordinates", [[]])[0]
        center_lon = sum(c[0] for c in coords) / max(len(coords), 1) if coords else 77.24
        center_lat = sum(c[1] for c in coords) / max(len(coords), 1) if coords else 28.62

        observations.append(
            UnifiedObservation(
                id=f"OBS-SAR-{p.get('id', idx+1)}",
                source_type="sar_satellite",
                source_id=props.get("polygon_id", f"SAR-{idx+1}"),
                observation_time=props.get("acquisition_date", now_iso),
                ingestion_time=now_iso,
                location_name=f"Inundation Zone ({props.get('area_sqkm', 0.1)} km²)",
                latitude=round(center_lat, 5),
                longitude=round(center_lon, 5),
                classification=props.get("severity", "medium"),
                extent_or_depth={
                    "type": "inundation_area_sqkm",
                    "value": props.get("area_sqkm", 0.1),
                    "mean_backscatter_db": props.get("mean_backscatter_db", -20.0),
                },
                confidence=props.get("confidence_score", 0.90),
                verification_status="sar_calibrated_detection",
                evidence_url=None,
            )
        )

    # 2. Camera Stations
    stations = await db.get_camera_stations()
    for s in stations:
        observations.append(
            UnifiedObservation(
                id=f"OBS-CAM-{s['id']}",
                source_type="camera_edge",
                source_id=s["id"],
                observation_time=s.get("last_updated", now_iso),
                ingestion_time=now_iso,
                location_name=s["name"],
                latitude=s["latitude"],
                longitude=s["longitude"],
                classification=s.get("status", "safe"),
                extent_or_depth={
                    "type": "water_level_cm",
                    "value": s.get("water_level_cm", 0.0),
                    "hazard": s.get("hazard", "None"),
                },
                confidence=0.95,
                verification_status="edge_yolov8_telemetry",
                evidence_url=s.get("image_url"),
            )
        )

    # 3. Citizen Reports
    citizen_reports = await db.get_citizen_reports()
    for r in citizen_reports:
        observations.append(
            UnifiedObservation(
                id=f"OBS-CIT-{r['id']}",
                source_type="citizen_report",
                source_id=r["id"],
                observation_time=r.get("created_at", now_iso),
                ingestion_time=r.get("created_at", now_iso),
                location_name=r["location_name"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                classification="danger" if r.get("verified") else "caution",
                extent_or_depth={
                    "type": "hazard_description",
                    "hazard_type": r.get("hazard_type"),
                    "description": r.get("description"),
                },
                confidence=0.85 if r.get("verified") else 0.45,
                verification_status=r.get("verification_status", "pending_community"),
                evidence_url=r.get("image_url"),
            )
        )

    return observations
