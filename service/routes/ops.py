from __future__ import annotations

from fastapi import APIRouter, Depends

from jobs.sla_monitor import compute_sla_report
from service.security.key_rotation import rotation_status
from service.security.oidc import AuthContext, require_roles
from service.security.production_guard import production_control_status


router = APIRouter(prefix="/v1/ops", tags=["ops"])


@router.get("/sla")
def get_sla(auth: AuthContext = Depends(require_roles("admin", "ops_submitter"))):
    return compute_sla_report()


@router.get("/controls")
def get_controls(auth: AuthContext = Depends(require_roles("admin"))):
    return {
        "key_rotation": rotation_status(),
        "production_guard": production_control_status(),
    }
