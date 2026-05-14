"""URL-safe slug generation for public claim pages."""

import re
from uuid import UUID

from slugify import slugify


def public_slug_for_claim(canonical_text: str, claim_id: UUID) -> str:
    """Build a unique, readable slug for routing and SEO."""
    base = slugify(canonical_text[:96], lowercase=True) or "claim"
    suffix = str(claim_id).replace("-", "")[:10]
    cleaned = re.sub(r"-+", "-", f"{base}-{suffix}").strip("-")
    return cleaned[:155]
