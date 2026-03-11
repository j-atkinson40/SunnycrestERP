import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


RESERVED_SLUGS = {"www", "api", "app", "admin", "mail", "ftp", "default", "support"}


def validate_company_slug(v: str) -> str:
    v = v.lower().strip()
    if len(v) < 3 or len(v) > 63:
        raise ValueError("Slug must be 3-63 characters")
    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", v):
        raise ValueError(
            "Slug must be lowercase alphanumeric with hyphens, "
            "no leading/trailing hyphens"
        )
    if v in RESERVED_SLUGS:
        raise ValueError(f"'{v}' is a reserved slug")
    return v


class CompanyCreate(BaseModel):
    name: str
    slug: str

    @field_validator("slug")
    @classmethod
    def check_slug(cls, v: str) -> str:
        return validate_company_slug(v)


class CompanyResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyRegisterRequest(BaseModel):
    """Create a new company along with its first admin user."""

    company_name: str
    company_slug: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str

    @field_validator("company_slug")
    @classmethod
    def check_slug(cls, v: str) -> str:
        return validate_company_slug(v)
