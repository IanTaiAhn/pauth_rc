"""
Pydantic models for the compiled policy checklist JSON.
This is the source of truth for the JSON shape.
"""

from typing import Literal, Optional
from pydantic import BaseModel


class TemplateItem(BaseModel):
    field: str
    label: str
    help_text: Optional[str] = None
    input_type: str
    icd10_codes: Optional[list[str]] = None
    detail_fields: Optional[list[dict]] = None


class TemplateSection(BaseModel):
    id: str
    title: str
    description: str
    requirement_type: Literal["any", "all", "count_gte"]
    threshold: Optional[int] = None
    help_text: Optional[str] = None
    items: list[TemplateItem]


class ExceptionPathway(BaseModel):
    id: str
    title: str
    description: str
    waives: list[str]
    requirement_type: Literal["any", "all", "count_gte"]
    threshold: Optional[int] = None
    help_text: Optional[str] = None
    items: list[TemplateItem]


class Exclusion(BaseModel):
    id: str
    title: str
    description: str
    severity: str = "hard_stop"


class PolicyTemplate(BaseModel):
    payer: str
    cpt_code: str
    policy_source: Optional[str] = None
    policy_effective_date: Optional[str] = None
    checklist_sections: list[TemplateSection]
    exception_pathways: list[ExceptionPathway]
    exclusions: list[Exclusion]
    denial_prevention_tips: list[str]
    submission_reminders: list[str]
    validation_errors: list[str] = []
    model: Optional[str] = None


class StepDebugInfo(BaseModel):
    """Debug metadata for a single pipeline step."""
    step_name: str
    prompt: str
    raw_response: str
    parsed_output: dict


class CompilationDebug(BaseModel):
    """Debug metadata for the full two-step compilation pipeline."""
    step1_structure: StepDebugInfo
    step2_detail: StepDebugInfo


class CompilationResponse(BaseModel):
    """API response that includes the compiled template and optional debug data."""
    template: PolicyTemplate
    debug: Optional[CompilationDebug] = None


class SkeletonResponse(BaseModel):
    """API response for the POST /api/structure endpoint (Step 1 only)."""
    payer: str
    cpt_code: str
    checklist_sections: list[dict]
    exception_pathways: list[dict]
    exclusions: list[dict]
    saved: bool = False
