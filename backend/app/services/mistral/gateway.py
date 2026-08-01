import asyncio
import json
from functools import lru_cache

from mistralai import Mistral

from backend.app.contracts.embeddings import validate_embeddings
from backend.app.contracts.normalization import json_safe, normalize_text
from backend.app.core.config import settings
from backend.app.schemas.mistral import (
    AuditClaim,
    ClaimExtractionResponse,
    ExtractedClaim,
    TransformClassificationResponse,
    TransformType,
)
from backend.app.services.mistral.prompts import (
    CLAIM_EXTRACTION_SYSTEM_PROMPT,
    TRANSFORM_CLASSIFICATION_SYSTEM_PROMPT,
)


class MistralServiceError(RuntimeError):
    """Raised when a Mistral response cannot satisfy the pipeline contract."""


class MistralGateway:
    EMBEDDING_BATCH_SIZE = 64

    def __init__(self, client: Mistral | None = None) -> None:
        if not settings.has_mistral_key:
            raise MistralServiceError("MISTRAL_API_KEY is not configured.")

        self._client = client or Mistral(api_key=settings.mistral_api_key)
        self._chat_limit = asyncio.Semaphore(8)

    async def extract_claims(self, text: str) -> list[ExtractedClaim]:
        text = normalize_text(text)
        if not text:
            return []

        async with self._chat_limit:
            response = await self._client.chat.parse_async(
                response_format=ClaimExtractionResponse,
                model=settings.mistral_extract_model,
                messages=[
                    {"role": "system", "content": CLAIM_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0,
                max_tokens=2_048,
            )

        parsed = self._parsed_choice(response)
        # An unanchored model span is dropped rather than repaired.
        return [
            claim
            for claim in parsed.claims
            if claim.source_span
            and claim.subject
            and claim.predicate
            and claim.object
            and claim.source_span in text
        ]

    async def classify_transforms(
        self,
        upstream: list[AuditClaim],
        downstream: list[AuditClaim],
    ) -> TransformClassificationResponse:
        if not upstream and not downstream:
            return TransformClassificationResponse(transforms=[])

        upstream_ids = {claim.id for claim in upstream}
        downstream_ids = {claim.id for claim in downstream}

        async with self._chat_limit:
            response = await self._client.chat.parse_async(
                response_format=TransformClassificationResponse,
                model=settings.mistral_transform_model,
                messages=[
                    {
                        "role": "system",
                        "content": TRANSFORM_CLASSIFICATION_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": self._transform_message(upstream, downstream),
                    },
                ],
                temperature=0,
                max_tokens=4_096,
            )

        parsed = self._parsed_choice(response)
        valid_transforms = [
            transform
            for transform in parsed.transforms
            if (
                transform.upstream_claim_id is None
                or transform.upstream_claim_id in upstream_ids
            )
            and (
                transform.downstream_claim_id is None
                or transform.downstream_claim_id in downstream_ids
            )
            and bool(transform.rationale.strip())
        ]
        supported_downstream_ids = {
            transform.downstream_claim_id
            for transform in valid_transforms
            if transform.upstream_claim_id is not None
            and transform.downstream_claim_id is not None
            and transform.transform_type != TransformType.UNSUPPORTED_ADDITION
        }
        parsed.transforms = [
            transform
            for transform in valid_transforms
            if transform.transform_type != TransformType.UNSUPPORTED_ADDITION
            or (
                transform.upstream_claim_id is None
                and transform.downstream_claim_id is not None
                and transform.downstream_claim_id not in supported_downstream_ids
            )
        ]
        return parsed

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        texts = [normalize_text(text) for text in texts]
        if any(not text for text in texts):
            raise ValueError("Embedding inputs must contain non-empty text.")

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + self.EMBEDDING_BATCH_SIZE]
            response = await self._client.embeddings.create_async(
                model=settings.mistral_embed_model,
                inputs=batch,
                encoding_format="float",
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            embeddings.extend([list(item.embedding) for item in ordered])

        try:
            return validate_embeddings(embeddings, expected_count=len(texts))
        except (TypeError, ValueError, RuntimeError) as exc:
            raise MistralServiceError(f"Invalid Mistral embedding response: {exc}") from exc

    @staticmethod
    def _parsed_choice(response):
        if not response.choices or response.choices[0].message.parsed is None:
            raise MistralServiceError("Mistral returned no structured response.")
        return response.choices[0].message.parsed

    @staticmethod
    def _transform_message(
        upstream: list[AuditClaim],
        downstream: list[AuditClaim],
    ) -> str:
        def format_claim(claim: AuditClaim) -> str:
            qualifiers = {
                key: value
                for key, value in claim.qualifiers.items()
                if value not in (None, "", "unstated")
            }
            qualifier_text = (
                " "
                + json.dumps(
                    json_safe(qualifiers),
                    ensure_ascii=False,
                    sort_keys=True,
                    allow_nan=False,
                )
                if qualifiers
                else ""
            )
            return (
                f'[{claim.id}] ({claim.claim_type.value}) '
                f'"{claim.source_span}"{qualifier_text}'
            )

        upstream_text = "\n".join(format_claim(claim) for claim in upstream)
        downstream_text = "\n".join(format_claim(claim) for claim in downstream)
        return (
            f"UPSTREAM CLAIMS:\n{upstream_text}\n\n"
            f"DOWNSTREAM CLAIMS:\n{downstream_text}"
        )


@lru_cache
def get_mistral_gateway() -> MistralGateway:
    return MistralGateway()
