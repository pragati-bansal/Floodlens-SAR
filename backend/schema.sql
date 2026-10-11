-- Schema for FloodLens Supabase PostgreSQL Database

-- 1. Camera Stations Table
CREATE TABLE IF NOT EXISTS camera_stations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    area TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    water_level_cm DOUBLE PRECISION DEFAULT 0.0,
    status TEXT CHECK (status IN ('safe', 'caution', 'danger')) DEFAULT 'safe',
    hazard TEXT,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    image_url TEXT
);

-- 2. Citizen Reports Table
CREATE TABLE IF NOT EXISTS citizen_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    hazard_type TEXT NOT NULL,
    description TEXT,
    verified BOOLEAN DEFAULT FALSE,
    verification_status TEXT CHECK (verification_status IN ('verified_camera', 'rejected_clear', 'pending_community')) DEFAULT 'pending_community',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Hazard Logs (Edge telemetry audit trail)
CREATE TABLE IF NOT EXISTS hazard_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id TEXT NOT NULL REFERENCES camera_stations(id) ON DELETE CASCADE,
    water_depth_cm DOUBLE PRECISION NOT NULL,
    state INTEGER NOT NULL,
    status TEXT NOT NULL,
    hazard TEXT,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Agency Responder Profiles
CREATE TABLE IF NOT EXISTS agency_users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    agency_name TEXT NOT NULL, -- e.g., 'Delhi Police', 'Delhi Fire Service', 'AIIMS Emergency Ward'
    role TEXT CHECK (role IN ('police', 'fire', 'hospital', 'superadmin')) NOT NULL,
    badge_number TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Emergency Dispatch Log Table
CREATE TABLE IF NOT EXISTS emergency_dispatches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id TEXT REFERENCES camera_stations(id),
    dispatched_by UUID REFERENCES agency_users(id),
    agency_type TEXT NOT NULL,
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'critical')) DEFAULT 'high',
    notes TEXT,
    status TEXT CHECK (status IN ('dispatched', 'en_route', 'resolved')) DEFAULT 'dispatched',
    dispatched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Realtime publication
ALTER PUBLICATION supabase_realtime ADD TABLE emergency_dispatches;

-- RLS: Only authenticated responders can view/create dispatches
ALTER TABLE agency_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE emergency_dispatches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated read agency profiles"
    ON agency_users FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow agency dispatch insert"
    ON emergency_dispatches FOR INSERT TO authenticated WITH CHECK (true);

CREATE POLICY "Allow agency dispatch select"
    ON emergency_dispatches FOR SELECT TO authenticated USING (true);

-- Indexes for performant spatial and temporal queries
CREATE INDEX IF NOT EXISTS idx_camera_stations_status ON camera_stations(status);
CREATE INDEX IF NOT EXISTS idx_citizen_reports_created_at ON citizen_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hazard_logs_camera_id ON hazard_logs(camera_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_emergency_dispatches_created_at ON emergency_dispatches(dispatched_at DESC);
CREATE INDEX IF NOT EXISTS idx_emergency_dispatches_status ON emergency_dispatches(status);

-- 6. Sentinel-1 Satellite Scenes Catalog
CREATE TABLE IF NOT EXISTS satellite_scenes (
    scene_id TEXT PRIMARY KEY,
    satellite TEXT NOT NULL,
    sensor_mode TEXT NOT NULL,
    product_type TEXT NOT NULL,
    polarizations TEXT[] NOT NULL,
    acquisition_date TIMESTAMPTZ NOT NULL,
    orbit_direction TEXT CHECK (orbit_direction IN ('ASCENDING', 'DESCENDING')),
    min_lon DOUBLE PRECISION NOT NULL,
    min_lat DOUBLE PRECISION NOT NULL,
    max_lon DOUBLE PRECISION NOT NULL,
    max_lat DOUBLE PRECISION NOT NULL,
    region TEXT NOT NULL,
    is_pre_event BOOLEAN DEFAULT FALSE,
    source TEXT NOT NULL,
    resolution_m DOUBLE PRECISION DEFAULT 10.0,
    mean_backscatter_db DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. SAR Inundation Processing Jobs
CREATE TABLE IF NOT EXISTS processing_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT CHECK (status IN ('queued', 'processing', 'completed', 'failed')) DEFAULT 'queued',
    progress_pct INTEGER DEFAULT 0,
    region TEXT NOT NULL,
    post_event_scene_id TEXT REFERENCES satellite_scenes(scene_id),
    pre_event_scene_id TEXT REFERENCES satellite_scenes(scene_id),
    polarization TEXT DEFAULT 'VV',
    threshold_db DOUBLE PRECISION DEFAULT -16.0,
    total_inundated_area_sqkm DOUBLE PRECISION DEFAULT 0.0,
    polygons_count INTEGER DEFAULT 0,
    affected_roads_count INTEGER DEFAULT 0,
    method TEXT NOT NULL,
    confidence_level TEXT DEFAULT 'high',
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- 8. Georeferenced Flood Inundation Polygons
CREATE TABLE IF NOT EXISTS flood_polygons (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES processing_jobs(job_id) ON DELETE CASCADE,
    area_sqkm DOUBLE PRECISION NOT NULL,
    source TEXT NOT NULL,
    detection_method TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL,
    mean_backscatter_db DOUBLE PRECISION,
    acquisition_date TIMESTAMPTZ NOT NULL,
    water_type TEXT DEFAULT 'flood_inundation',
    severity TEXT CHECK (severity IN ('low', 'medium', 'high')) DEFAULT 'medium',
    geometry JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Road Segment Risk Assessments
CREATE TABLE IF NOT EXISTS road_risk_assessments (
    road_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    corridor TEXT NOT NULL,
    status TEXT CHECK (status IN ('safe', 'caution', 'impassable')) NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    intersecting_polygon_id TEXT REFERENCES flood_polygons(id) ON DELETE SET NULL,
    distance_to_flood_m DOUBLE PRECISION NOT NULL,
    flag_reason TEXT NOT NULL,
    evidence_source TEXT NOT NULL,
    coordinates JSONB NOT NULL,
    assessed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_satellite_scenes_region ON satellite_scenes(region);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_flood_polygons_job_id ON flood_polygons(job_id);
CREATE INDEX IF NOT EXISTS idx_road_risk_status ON road_risk_assessments(status);
