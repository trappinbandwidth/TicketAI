"""Authenticated Driver profile API and verification-data boundary."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.routes._common import get_db
from app.services.auth_rbac import require_role, verify_firebase_token
from app.services.driver_profile import DriverProfileService, PiiCipher

router = APIRouter(prefix="/driver/profile", tags=["driver-profile"])


class DriverAddress(BaseModel):
    street: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    zip: str = Field(pattern=r"^\d{5}(?:-\d{4})?$")


class DriverProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    middle_initial: str = Field(default="", max_length=1)
    last_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=32)
    dob: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    cdl_number: str = Field(min_length=1, max_length=40)
    cdl_state: str = Field(pattern=r"^[A-Z]{2}$")
    cdl_expiration: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    address: DriverAddress
    ssn_last4: str = Field(pattern=r"^\d{4}$")
    driver_role: Literal["company_driver", "owner_operator"]
    carrier_name: Optional[str] = Field(default=None, max_length=160)
    business_name: Optional[str] = Field(default=None, max_length=160)
    profile_image: str = Field(min_length=20, max_length=750_000)

    @model_validator(mode="after")
    def require_organization(self):
        if self.driver_role == "company_driver" and not (self.carrier_name or "").strip():
            raise ValueError("carrier_name is required for a company Driver.")
        if self.driver_role == "owner_operator" and not (self.business_name or "").strip():
            raise ValueError("business_name is required for an owner-operator.")
        return self


def _driver_claims(authorization: Optional[str]) -> dict:
    claims = require_role(verify_firebase_token(authorization), {"driver"})
    uid = claims.get("uid")
    if not isinstance(uid, str) or not uid:
        raise HTTPException(status_code=401, detail="Authenticated Driver identity is missing.")
    return claims


def _service() -> DriverProfileService:
    return DriverProfileService(get_db(), PiiCipher.from_env())


@router.get("")
def get_profile(authorization: Optional[str] = Header(None)):
    claims = _driver_claims(authorization)
    return _service().get(claims["uid"], phone=claims.get("phone_number"))


@router.put("")
def save_profile(body: DriverProfileUpdate, authorization: Optional[str] = Header(None)):
    claims = _driver_claims(authorization)
    return _service().save(claims["uid"], body, phone=claims.get("phone_number"))
