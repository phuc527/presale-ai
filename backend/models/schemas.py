from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class SetupOrRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(..., min_length=2, max_length=80)
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["admin", "presales"] = "presales"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=40)
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AgentConfigUpdate(BaseModel):
    provider: Literal["gemini", "openai", "anthropic", "ollama"]
    model_name: str = Field(..., min_length=2, max_length=80)
    auth_mode: Literal["api_key", "oauth_login", "local_none"]
    api_key: Optional[str] = Field(default=None, max_length=300)
    oauth_token: Optional[str] = Field(default=None, max_length=2000)
    oauth_account_email: Optional[str] = Field(default=None, max_length=120)
    base_url: Optional[str] = Field(default="", max_length=200)
    vendors: List[str] = Field(default_factory=list, max_length=25)
    technologies: List[str] = Field(default_factory=list, max_length=25)
    industries: List[str] = Field(default_factory=list, max_length=25)
    frameworks: List[str] = Field(default_factory=list, max_length=25)
    depth_level: Literal["executive", "architect", "deep_engineering"] = "architect"
    max_output_tokens: int = Field(default=1600, ge=256, le=8192)
    compression_level: Literal["off", "balanced", "aggressive"] = "balanced"
    cache_enabled: bool = True
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    system_prompt: str = Field(..., min_length=20, max_length=6000)

    @field_validator("vendors", "technologies", "industries", "frameworks")
    @classmethod
    def sanitize_tags(cls, items: List[str]) -> List[str]:
        cleaned = []
        for item in items:
            s = item.strip()[:80]
            if s and s not in cleaned:
                cleaned.append(s)
        return cleaned


class AgentRunRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=15000)
    focus_vendor: Optional[str] = Field(default="", max_length=80)
    focus_technology: Optional[str] = Field(default="", max_length=80)
    focus_industry: Optional[str] = Field(default="", max_length=80)
    depth_override: Optional[Literal["", "executive", "architect", "deep_engineering"]] = ""
    bypass_cache: bool = False


class PipelineDiscoveryRequest(BaseModel):
    deal_title: str = Field(..., min_length=2, max_length=150)
    customer_notes: str = Field(..., min_length=10, max_length=20000)
    focus_vendor: Optional[str] = Field(default="", max_length=80)
    focus_technology: Optional[str] = Field(default="", max_length=80)
    focus_industry: Optional[str] = Field(default="", max_length=80)


class PipelineSynthesizeRequest(BaseModel):
    deal_title: str = Field(..., min_length=2, max_length=150)
    customer_notes: str = Field(..., min_length=10, max_length=20000)
    ai1_output: str = Field(..., min_length=5, max_length=25000)
    ai2_output: str = Field(..., min_length=5, max_length=25000)
    architect_approval_notes: str = Field(default="", max_length=5000)


class ExportRequest(BaseModel):
    deal_title: str = Field(default="Enterprise_Solution_Proposal", max_length=120)
    ai1_output: str = Field(default="", max_length=30000)
    ai2_output: str = Field(default="", max_length=30000)
    ai3_output: str = Field(default="", max_length=30000)
    ai4_output: str = Field(default="", max_length=30000)
    architect_notes: str = Field(default="", max_length=10000)


class WhatsAppSimulateRequest(BaseModel):
    sender: str = Field(default="+84901234567", max_length=40)
    message: str = Field(..., min_length=1, max_length=4000)
