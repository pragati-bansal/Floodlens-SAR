# 🛰️ FloodLens — Space-Based Flood Inundation Mapping & Safe Routing for NDRF
## ORBITRON Spaceathon | Problem Statement 17

[![React](https://img.shields.io/badge/Frontend-React_19_+_Vite-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Sentinel-1](https://img.shields.io/badge/Remote_Sensing-Sentinel--1_C--band_SAR-005596?logo=satellite&logoColor=white)](https://sentinels.copernicus.eu/)
[![PostGIS](https://img.shields.io/badge/Spatial-Shapely_+_PostGIS-336791?logo=postgresql&logoColor=white)](https://postgis.net/)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind_CSS_v4-38B2AC?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![YOLOv8](https://img.shields.io/badge/Computer_Vision-YOLOv8_Segmentation-00FFFF?logo=ultralytics&logoColor=black)](https://github.com/ultralytics/ultralytics)
[![Leaflet](https://img.shields.io/badge/Maps-React_Leaflet-199900?logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**FloodLens** is an end-to-end geospatial intelligence and emergency decision-support platform designed for the **National Disaster Response Force (NDRF)** during severe monsoon flooding.

During extreme weather events, optical satellites fail due to dense cloud cover. FloodLens utilizes **Sentinel-1 Synthetic Aperture Radar (SAR)** as its primary all-weather sensing input, processing radar backscatter to delineate surface water inundation polygons, intersecting them with urban arterial roads, and calculating lower-risk candidate rescue routes.

---

## 🌟 Key Capabilities

### 1. 🛰️ Space-Based Sentinel-1 SAR Pipeline (Primary NDRF Input)
- **All-Weather C-Band Radar Sensing (5.405 GHz)**: Cloud-penetrating imagery acquisition in Interferometric Wide (IW) Ground Range Detected (GRD) mode (10m resolution).
- **Radiometric Calibration**: Raw radar digital numbers calibrated into Sigma Nought ($\sigma^0$) linear and decibel (dB) values.
- **Adaptive Speckle Filtering**: Spatial Lee adaptive filtering approximation to suppress multiplicative radar speckle noise while preserving riverbank and flood boundaries.
- **Bi-Temporal Change Detection**: Before-and-after event comparison ($\Delta \sigma^0 \le -3.5 \text{ dB}$) paired with amplitude thresholding ($\sigma^0 \le -16.0 \text{ dB}$ for VV) to isolate newly inundated surfaces from dry land.
- **Permanent-Water Exclusion**: Masks out perennial dry-season riverbeds to prevent misclassifying normal river bodies as newly flooded regions.
- **Topological Vector Polygonization**: Automatic contour-to-vectorization with topology repair (`shapely.validation.make_valid`), producing georeferenced WGS84 GeoJSON features with area ($\text{km}^2$), mean backscatter, and confidence scoring.

### 2. 🚧 Flood-Road Spatial Intersection & NDRF Candidate Routing
- **Spatial Buffer & Intersection**: Evaluates road LineStrings against detected SAR flood polygons. Classifies corridors into `impassable` (direct intersection), `caution` (<300m buffer), and `safe` (clear).
- **Dynamic NetworkX Dijkstra Routing**: Applies dynamic hazard penalties (infinite weight for impassable corridors) to compute lower-risk candidate alternative routes.
- **OSRM Street Geometry Snapping**: Connects waypoints to OpenStreetMap geometry for realistic street-level navigation.
- **Explainable Decision Support**: Transparently displays avoided flooded road corridors, safety ratings, and NDRF operational disclaimers.

### 3. 👁️ Supplementary Edge Camera Telemetry & Ground Truth
- **YOLOv8 Edge Segmentation**: Water depth markers (cm) and severity classifications from CCTV feeds at critical transit junctions.
- **Clean Source Normalization**: SAR surface extent and camera water depths are kept logically separate with transparent provenance.

### 4. 👥 Citizen Hazard Reporting & Admin Portal
- **500m Proximity Verification**: Automated cross-referencing with nearby sensor stations.
- **Municipal Command Dashboard**: Role-based access control, broadcast advisories, and emergency dispatch logs.

---

## 📁 Repository Structure

```
floodlens/
├── .gitignore                   # Comprehensive root exclusions (env, venv, node_modules)
├── README.md                    # Project documentation & architecture overview
│
├── backend/                     # FastAPI Python Backend
│   ├── app/
│   │   ├── api/                 # API routers:
│   │   │   ├── routes_admin.py        # Municipal alerts & admin controls
│   │   │   ├── routes_cameras.py      # Camera stations & telemetry feeds
│   │   │   ├── routes_citizen.py      # Citizen crowdsourced reporting
│   │   │   ├── routes_edge.py         # AI camera snapshot analysis
│   │   │   └── routes_navigation.py   # Safe routing & detour calculations
│   │   ├── core/                # App config, database clients, CORS
│   │   ├── schemas/             # Pydantic schemas for requests/responses
│   │   ├── services/            # Core business logic:
│   │   │   ├── router.py              # Flood graph pathfinding & OSRM client
│   │   │   ├── verifier.py            # Citizen report verification algorithms
│   │   │   └── water_seg_service.py   # YOLOv8 segmentation & HUD renderer
│   │   ├── static/              # Edge camera snapshots & static assets
│   │   ├── weights/             # AI model weights (water_seg.pt)
│   │   ├── __init__.py
│   │   └── main.py              # Application entrypoint & middleware
│   ├── .env.example             # Backend environment template
│   ├── requirements.txt         # Python dependencies
│   ├── schema.sql               # PostgreSQL / Supabase schema definition
│   ├── seed_data.py             # Database seeder for Delhi camera stations
│   ├── test_backend.py          # FastAPI endpoint integration test suite
│   ├── test_images/             # Sample monsoon camera test images
│   └── test_water_model.py      # CLI benchmark & test tool for segmentation
│
└── frontend/                    # React 19 + TypeScript + Vite Frontend
    ├── public/                  # Static assets & camera preview mocks
    ├── src/
    │   ├── assets/              # Branding and icons
    │   ├── components/          # Reusable UI components:
    │   │   ├── CameraCard.tsx         # Camera telemetry & snapshot card
    │   │   ├── CameraWebcamModal.tsx  # Edge webcam test simulator
    │   │   ├── DepthBadge.tsx         # Water depth indicator badge
    │   │   ├── MiniMapPreview.tsx     # Hero live radar preview map
    │   │   ├── Navbar.tsx / Footer    # Navigation & layout chrome
    │   │   └── StatusBadge.tsx        # Standardized status tags
    │   ├── context/             # AuthContext (Emergency Admin session)
    │   ├── data/                # Fallback mock datasets & Delhi coordinates
    │   ├── hooks/               # Custom hooks (telemetry polling, reports)
    │   ├── lib/                 # API client & Supabase connector
    │   ├── pages/               # App views:
    │   │   ├── Home.tsx               # 2-Column hero, mini-map, search & stats
    │   │   ├── MapPage.tsx            # Full GIS Safe Roads Map & Routing
    │   │   ├── CamerasPage.tsx        # CCTV monitoring station grid
    │   │   ├── ReportPage.tsx         # Citizen incident report form
    │   │   ├── AboutPage.tsx          # Architecture and methodology
    │   │   └── admin/                 # Admin login & dispatch dashboard
    │   ├── types/               # TypeScript interfaces
    │   ├── utils/               # Haversine distance, time utilities, colors
    │   ├── App.tsx              # Router configuration
    │   ├── index.css            # Tailwind CSS v4 styling & animations
    │   └── main.tsx             # React entrypoint
    ├── .env.example             # Frontend environment template
    ├── package.json             # NPM dependencies & scripts
    └── vite.config.ts           # Vite bundler configuration
```

---

## 🛠️ Tech Stack

| Domain | Technologies |
|---|---|
| **Frontend Framework** | [React 19](https://react.dev/), [TypeScript](https://www.typescriptlang.org/), [Vite](https://vitejs.dev/) |
| **Styling & Design** | [Tailwind CSS v4](https://tailwindcss.com/), Glassmorphism, HSL earth palette |
| **Maps & GIS** | [Leaflet](https://leafletjs.com/), [React-Leaflet](https://react-leaflet.js.org/), [OSRM API](https://project-osrm.org/) |
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [Pydantic v2](https://docs.pydantic.dev/) |
| **Computer Vision** | [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics), [OpenCV](https://opencv.org/), [NumPy](https://numpy.org/) |
| **Database & Auth** | [Supabase](https://supabase.com/) (PostgreSQL), In-Memory Fallback Engine |

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** (v18 or later) & **npm**
- **Python** (v3.10 or later) & **pip**
- *(Optional)* Git LFS or direct weights placement (`backend/app/weights/water_seg.pt`)

---

### 1. Backend Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a Python virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env if configuring Supabase credentials (optional; fallback engine works out of the box)

# 5. Start the FastAPI server with auto-reload
uvicorn app.main:app --reload --port 8000
```

- **API Documentation (Swagger UI):** `http://localhost:8000/docs`
- **Alternative ReDoc UI:** `http://localhost:8000/redoc`

---

### 2. Frontend Setup

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Configure environment variables
cp .env.example .env

# 4. Start the Vite development server
npm run dev
```

- **Web Application URL:** `http://localhost:5173`

---

## 🧪 Testing & Verification

### Running Backend Unit & Integration Tests
```bash
cd backend
python test_backend.py
```

### Running Sentinel-1 SAR Pipeline & NDRF Routing Tests
```bash
cd backend
python test_satellite_pipeline.py
```

### Testing the AI Water Segmentation Model
```bash
cd backend
python test_water_model.py
```
This tests the YOLOv8 segmentation on sample underpass images in `test_images/` and outputs telemetry metrics to the terminal.

### Building & Type-Checking Frontend
```bash
cd frontend
npm run build
npm run lint
```

---

## 📡 Core API Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/cameras` | List all monitored camera stations & real-time telemetry |
| `GET` | `/api/cameras/{id}` | Detailed telemetry and latest analyzed snapshot for a station |
| `POST` | `/api/navigation/safe-route` | Calculate a flood-avoiding safe route between two points |
| `POST` | `/api/edge/segment` | Run YOLOv8 segmentation on uploaded image with visual HUD |
| `GET` | `/api/citizen/reports` | Retrieve active citizen waterlogging hazard reports |
| `POST` | `/api/citizen/reports` | Submit a new crowdsourced flood observation |
| `GET` | `/api/admin/dashboard` | Emergency services situational summary and alert feeds |
| `POST` | `/api/admin/broadcast` | Broadcast municipal flood warning advisories |

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request or file an issue:
1. Fork the project
2. Create your feature branch (`git checkout -b feature/NewFeature`)
3. Commit your changes (`git commit -m 'Add NewFeature'`)
4. Push to the branch (`git push origin feature/NewFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
