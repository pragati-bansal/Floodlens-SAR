export type StationStatus = 'safe' | 'caution' | 'danger';

export interface CameraStation {
  id: string;
  name: string;
  area?: string;
  latitude: number;
  longitude: number;
  water_level_cm: number;
  status: StationStatus;
  hazard?: string | null;
  last_updated?: string;
  image_url?: string;
  imageUrl?: string;
  snapshot_url?: string;
  snapshotUrl?: string;
}

export type HazardType =
  | 'Deep Water'
  | 'Small Flood'
  | 'Fallen Tree'
  | 'Broken Wire'
  | 'Big Hole in Road';

export type VerificationStatus =
  | 'verified_camera'
  | 'rejected_clear'
  | 'pending_community';

export interface CitizenReport {
  id: string;
  location_name: string;
  latitude: number;
  longitude: number;
  hazard_type: HazardType;
  description?: string;
  image_url?: string;
  verified: boolean;
  verification_status?: VerificationStatus;
  created_at: string;
  nearest_station_id?: string;
  distance_to_station_m?: number;
}

export interface RouteWaypoint {
  station_id: string;
  name: string;
  latitude: number;
  longitude: number;
  water_level_cm: number;
  status: StationStatus;
}

export interface RouteSummary {
  total_distance_km: number;
  estimated_duration_min: number;
  safety_rating: 'safe' | 'caution_advisory' | 'impassable';
  waypoints_count: number;
  danger_stations_avoided: string[];
  caution_zones_encountered: string[];
}

export interface SafeRouteResponse {
  success: boolean;
  message: string;
  summary: RouteSummary;
  path_stations: RouteWaypoint[];
  coordinates: [number, number][]; // [lat, lng][]
}

/* ----------------- Emergency Services Portal Types ----------------- */

export type AgencyRole = 'police' | 'fire' | 'hospital' | 'superadmin';

export interface AgencyUser {
  id: string;
  email: string;
  agency_name: string;
  role: AgencyRole;
  badge_number?: string;
  created_at?: string;
  token?: string;
}

export type DispatchPriority = 'low' | 'medium' | 'high' | 'critical';
export type DispatchStatus = 'dispatched' | 'en_route' | 'resolved';

export interface EmergencyDispatch {
  id: string;
  camera_id: string;
  dispatched_by?: string;
  agency_type: string;
  priority: DispatchPriority;
  notes?: string;
  status: DispatchStatus;
  dispatched_at: string;
  camera_name?: string;
  camera_area?: string;
  responder_agency?: string;
  responder_badge?: string;
}

export interface RawCameraFeed {
  id: string;
  name: string;
  area?: string;
  latitude: number;
  longitude: number;
  water_level_cm: number;
  status: StationStatus;
  hazard: string;
  last_updated?: string;
  raw_feed_url: string;
  segmentation_overlay_url: string;
  detected_hazards: string[];
  segmentation_metrics: {
    water_segmentation_pixels_pct?: number;
    flow_velocity_est?: string;
    submerged_curb_depth_cm?: number;
    optical_resolution?: string;
    encoder_latency_ms?: number;
    mask2former_inference_ms?: number;
    [key: string]: any;
  };
}

/* ----------------- ORBITRON Spaceathon SAR Satellite & NDRF Types ----------------- */

export interface SatelliteScene {
  scene_id: string;
  satellite: string;
  sensor_mode: string;
  product_type: string;
  polarizations: string[];
  acquisition_date: string;
  orbit_direction: 'ASCENDING' | 'DESCENDING';
  bbox: [number, number, number, number];
  region: string;
  is_pre_event: boolean;
  source: string;
  resolution_m: number;
  orbit_number?: number;
  mean_backscatter_db?: number;
}

export interface ProcessingJob {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress_pct: number;
  region: string;
  created_at: string;
  completed_at?: string;
  post_event_scene_id: string;
  pre_event_scene_id?: string;
  polarization: string;
  threshold_db: number;
  total_inundated_area_sqkm: number;
  polygons_count: number;
  affected_roads_count: number;
  method: string;
  confidence_level: string;
  error_message?: string;
  metadata?: Record<string, any>;
}

export interface FloodPolygonProperties {
  polygon_id: string;
  job_id: string;
  area_sqkm: number;
  source: string;
  detection_method: string;
  confidence_score: number;
  mean_backscatter_db: number;
  acquisition_date: string;
  water_type: string;
  severity: 'low' | 'medium' | 'high';
}

export interface FloodPolygonFeature {
  type: 'Feature';
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: number[][][] | number[][][][];
  };
  properties: FloodPolygonProperties;
}

export interface FloodFeatureCollection {
  type: 'FeatureCollection';
  job_id?: string;
  region?: string;
  acquisition_date?: string;
  features: FloodPolygonFeature[];
  total_inundated_area_sqkm: number;
  metadata?: Record<string, any>;
}

export interface RoadRiskAssessment {
  road_id: string;
  name: string;
  corridor: string;
  status: 'impassable' | 'caution' | 'safe';
  risk_score: number;
  intersecting_polygon_id?: string | null;
  distance_to_flood_m: number;
  flag_reason: string;
  evidence_source: string;
  coordinates: [number, number][]; // [[lat, lon], ...]
  assessed_at: string;
}

export interface FlaggedSegmentAvoided {
  road_id: string;
  name: string;
  status: string;
  risk_score: number;
  flag_reason: string;
  flood_evidence: string;
}

export interface CandidateRouteResult {
  success: boolean;
  candidate_type: string;
  summary: {
    total_distance_km: number;
    estimated_duration_min: number;
    safety_rating: 'safe' | 'caution_advisory' | 'impassable';
    waypoints_count: number;
    nodes_traversed?: string[];
    avoided_flooded_corridors_count?: number;
  };
  coordinates: [number, number][]; // [[lat, lon], ...]
  flagged_segments_avoided: FlaggedSegmentAvoided[];
  safety_disclaimer: string;
  calculated_at: string;
}

export interface UnifiedObservation {
  id: string;
  source_type: 'sar_satellite' | 'camera_edge' | 'citizen_report';
  source_id: string;
  observation_time: string;
  ingestion_time: string;
  location_name: string;
  latitude: number;
  longitude: number;
  classification: string;
  extent_or_depth: Record<string, any>;
  confidence: number;
  verification_status: string;
  evidence_url?: string | null;
}
