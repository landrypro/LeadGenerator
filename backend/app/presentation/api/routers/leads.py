from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ....application.errors import AddressGenerationInProgress, EmptyExportError, PlacesProviderError
from ..dependencies import ContainerDependency
from ..mappers import to_domain_lead, to_generation_response, to_search_criteria
from ..schemas import ExportRequest, LeadGenerationRequest, LeadGenerationResponse

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("/search", response_model=LeadGenerationResponse)
async def search_leads(
    request: LeadGenerationRequest,
    container: ContainerDependency,
) -> LeadGenerationResponse:
    if not container.settings.google_maps_api_key:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_MAPS_API_KEY n’est pas configurée sur le serveur.",
        )
    try:
        result = await container.generate_leads.execute(
            to_search_criteria(request),
            request.requester.business_address,
        )
        return to_generation_response(result, request)
    except AddressGenerationInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Une génération est déjà en cours pour cette adresse professionnelle. "
                "Réessayez lorsqu’elle sera terminée."
            ),
        ) from exc
    except PlacesProviderError as exc:
        status = 429 if exc.status_code == 429 else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/export")
async def export_leads(payload: ExportRequest, container: ContainerDependency) -> Response:
    try:
        content = container.export_leads.execute(
            [to_domain_lead(lead) for lead in payload.leads],
            payload.search,
        )
    except EmptyExportError as exc:
        raise HTTPException(status_code=400, detail="Aucun lead à exporter.") from exc

    filename = f"leads-google-maps-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
