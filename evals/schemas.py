"""Pydantic schemas for structured evaluation output."""

from pydantic import BaseModel, Field


class SkillEvidence(BaseModel):
    name: str
    found: bool
    years_experience: float | None = None
    evidence: str = Field(
        description="Direct quote or snippet showing how the skill was demonstrated, or why it was not found."
    )


class ResumeScore(BaseModel):
    score: int = Field(ge=0, le=100, description="Overall matching score from 0 to 100.")
    skills: list[SkillEvidence] = Field(description="Evidence breakdown per required and preferred skill.")
    reason: str = Field(description="Concise 1-3 sentence summary explaining the score.")
