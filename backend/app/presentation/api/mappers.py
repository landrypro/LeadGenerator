from ...application.models import SearchCriteria
from ...application.use_cases.generate_leads import GenerateLeadsResult
from ...domain.lead import Lead as DomainLead
from .schemas import Lead, LeadGenerationRequest, LeadGenerationResponse, SearchRequest, SearchStats


def to_search_criteria(request: SearchRequest) -> SearchCriteria:
    return SearchCriteria(**request.model_dump(exclude={"requester"}))


def to_domain_lead(lead: Lead) -> DomainLead:
    return DomainLead(**lead.model_dump())


def to_generation_response(
    result: GenerateLeadsResult,
    request: LeadGenerationRequest,
) -> LeadGenerationResponse:
    return LeadGenerationResponse(
        leads=[Lead.model_validate(lead, from_attributes=True) for lead in result.search.leads],
        stats=SearchStats.model_validate(result.search.stats, from_attributes=True),
        generated_at=result.search.generated_at,
        map_snapshot_token=result.map_snapshot_token,
        search_parameters=SearchRequest.model_validate(request.model_dump(exclude={"requester"})),
    )
