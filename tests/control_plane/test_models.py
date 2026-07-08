from axiom_ops.control_plane.models import IncidentCreate
from axiom_ops.control_plane.repository import IncidentRepository


def test_request_fingerprint_is_stable_and_payload_sensitive() -> None:
    first = IncidentCreate(
        title="Inventory latency",
        service="inventory-service",
        severity="SEV2",
        summary="threshold exceeded",
    )
    same = IncidentCreate.model_validate(first.model_dump())
    changed = first.model_copy(update={"summary": "another signal"})

    assert IncidentRepository._fingerprint(first) == IncidentRepository._fingerprint(same)
    assert IncidentRepository._fingerprint(first) != IncidentRepository._fingerprint(changed)
