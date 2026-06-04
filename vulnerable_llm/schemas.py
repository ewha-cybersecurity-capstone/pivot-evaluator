from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class GenerateParams(BaseModel):
    temperature: Optional[float] = Field(default=None, description="무작위성 제어(서버가 0으로 강제할 수 있음)")
    max_tokens: Optional[int] = Field(default=None, description="최대 생성 토큰 수(서버 상한 적용)")


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="변형 프롬프트 p")

    bucket_id: Optional[str] = Field(default="LLM01_PROMPT_INJECTION", description="버킷 식별자")

    seed_id: Optional[str] = Field(default=None, description="Seed prompt 식별자(선택)")
    mutation_id: Optional[str] = Field(default=None, description="Mutation 샘플/전략 식별자(선택)")
    run_id: Optional[str] = Field(default=None, description="실험 실행 ID(선택)")

    triggers: Optional[List[str]] = Field(default=None, description="encoding detector용 평문 페이로드(선택)")

    context: Optional[str] = Field(default=None, description="외부 컨텍스트(선택)")

    params: Optional[GenerateParams] = Field(default_factory=GenerateParams)


class GenerateResponse(BaseModel):
    response: str
    meta: Dict[str, Any]