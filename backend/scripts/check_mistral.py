import asyncio

from backend.app.core.config import settings
from backend.app.contracts.normalization import normalize_text
from backend.app.schemas.mistral import AuditClaim, ClaimType
from backend.app.services.mistral import get_mistral_gateway


async def check() -> None:
    gateway = get_mistral_gateway()

    source = normalize_text(
        "Cafe\u0301 customer \U0001f469\u200d\U0001f4bb says: “I was charged twice” "
        "and cannot find where to dispute it.\x00"
    )
    claims = await gateway.extract_claims(source)
    if not claims or any(claim.source_span not in source for claim in claims):
        raise RuntimeError("Claim extraction did not return anchored claims.")

    embeddings = await gateway.embed_texts(
        [source, "東京 customers report billing friction \U0001f680."]
    )
    if len(embeddings) != 2 or not embeddings[0]:
        raise RuntimeError("Embedding response was incomplete.")

    transforms = await gateway.classify_transforms(
        upstream=[
            AuditClaim(
                id="TICKET-1:v1#C0",
                claim_type=ClaimType.PROBLEM,
                source_span="I was charged twice",
                qualifiers={
                    "severity": "high",
                    "quantity": "twice",
                    "locale": "東京",
                },
            ),
            AuditClaim(
                id="TICKET-1:v1#C1",
                claim_type=ClaimType.PROBLEM,
                source_span="cannot find where to dispute it",
                qualifiers={"severity": "medium"},
            ),
        ],
        downstream=[
            AuditClaim(
                id="SUMMARY-1:v1#C0",
                claim_type=ClaimType.PROBLEM,
                source_span="Customers report billing friction",
            )
        ],
    )
    if not transforms.transforms:
        raise RuntimeError("Transform classification returned no transforms.")

    print("mistral_configuration=ok")
    print(f"extract_model={settings.mistral_extract_model}")
    print(f"anchored_claims={len(claims)}")
    print(f"embed_model={settings.mistral_embed_model}")
    print(f"embedding_count={len(embeddings)}")
    print(f"embedding_dimensions={len(embeddings[0])}")
    print(f"transform_model={settings.mistral_transform_model}")
    print(
        "transform_types="
        + ",".join(transform.transform_type.value for transform in transforms.transforms)
    )


if __name__ == "__main__":
    asyncio.run(check())
