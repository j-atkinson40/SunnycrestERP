from datetime import datetime

from pydantic import BaseModel, Field


class CompanyHierarchyNode(BaseModel):
    id: str
    name: str
    slug: str
    hierarchy_level: str | None = None
    hierarchy_path: str | None = None
    parent_company_id: str | None = None
    is_active: bool = True
    children: list["CompanyHierarchyNode"] = []

    class Config:
        from_attributes = True


class SetParentRequest(BaseModel):
    parent_company_id: str | None = Field(
        None, description="ID of the parent company, or null to detach"
    )
    hierarchy_level: str | None = Field(
        None, description="corporate, regional, or location"
    )


class HierarchyResponse(BaseModel):
    tree: list[CompanyHierarchyNode]
    total_companies: int


class CompanyChildItem(BaseModel):
    id: str
    name: str
    slug: str
    hierarchy_level: str | None = None
    is_active: bool = True
    children_count: int = 0

    class Config:
        from_attributes = True
