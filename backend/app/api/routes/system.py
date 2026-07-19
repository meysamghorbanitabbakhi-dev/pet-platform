from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.contracts import PolicyResponse
from app.core.config import Settings, get_settings
from app.core.policies import LaunchPolicies

router = APIRouter(prefix="/system", tags=["system"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/policies", response_model=PolicyResponse)
async def policies(settings: SettingsDependency) -> PolicyResponse:
    return PolicyResponse.model_validate(asdict(LaunchPolicies.from_settings(settings)))
