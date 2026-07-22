from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .excel import build_workbook
from .generation_lock import AddressGenerationInProgress, AddressGenerationRegistry
from .map_snapshot import build_static_map_url
from .models import ExportRequest, LeadGenerationRequest, MapSnapshotRequest, SearchResponse
from .places import GooglePlacesClient, GooglePlacesError, GooglePlacesSettings
from .search_service import LeadSearchService

generation_registry = AddressGenerationRegistry()

app = FastAPI(title="Google Maps Lead Generator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, bool | str]:
    return {"status": "ok", "google_api_key_configured": bool(os.getenv("GOOGLE_MAPS_API_KEY"))}


@app.post("/api/leads/search", response_model=SearchResponse)
async def search_leads(request: LeadGenerationRequest) -> SearchResponse:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_MAPS_API_KEY n’est pas configurée sur le serveur.")
    client = GooglePlacesClient(GooglePlacesSettings(api_key=api_key))
    try:
        async with generation_registry.hold(request.requester.business_address):
            return await LeadSearchService(client).search(request)
    except AddressGenerationInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail="Une génération est déjà en cours pour cette adresse professionnelle. Réessayez lorsqu’elle sera terminée.",
        ) from exc
    except GooglePlacesError as exc:
        status = 429 if exc.status_code == 429 else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@app.post("/api/leads/export")
async def export_leads(payload: ExportRequest) -> Response:
    if not payload.leads:
        raise HTTPException(status_code=400, detail="Aucun lead à exporter.")
    content = build_workbook(payload)
    filename = f"leads-google-maps-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/map/snapshot")
async def map_snapshot(payload: MapSnapshotRequest) -> Response:
    api_key = (os.getenv("GOOGLE_MAPS_STATIC_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY", "")).strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Aucune clé Google Maps n’est configurée pour la carte.")
    url = build_static_map_url(payload, api_key)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            google_response = await client.get(url)
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise HTTPException(status_code=502, detail="La carte Google est temporairement indisponible.") from exc
    if google_response.is_error or not google_response.headers.get("content-type", "").startswith("image/"):
        raise HTTPException(
            status_code=502,
            detail="Google Maps a refusé la capture. Vérifiez que Maps Static API est activée pour la clé.",
        )
    return Response(
        content=google_response.content,
        media_type=google_response.headers.get("content-type", "image/png"),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


frontend_dist = Path(__file__).resolve().parents[2] / "client" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
