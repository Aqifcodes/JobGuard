import re
from urllib.parse import urlparse

from .models import JobListing


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def is_valid_job(job: JobListing) -> bool:
    """
    Basic quality checks.

    This does NOT claim that a job is guaranteed genuine.
    It only removes obviously unusable results.
    """

    if not job.title:
        return False

    if not job.company:
        return False

    if not job.url:
        return False

    parsed = urlparse(job.url)

    if parsed.scheme not in {"http", "https"}:
        return False

    if not parsed.netloc:
        return False

    return True


def deduplicate_jobs(jobs):
    seen = set()
    unique = []

    for job in jobs:
        key = (
            normalize_text(job.title),
            normalize_text(job.company),
            normalize_text(job.location),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(job)

    return unique


def score_job(job: JobListing, role: str, location: str = "") -> float:
    """
    Relevance score for ranking results.

    This is NOT a scam score.
    """

    score = 0.0

    role_text = normalize_text(role)
    title = normalize_text(job.title)
    description = normalize_text(job.description)
    job_location = normalize_text(job.location)

    role_words = {
        word
        for word in re.findall(r"[a-z0-9+#.]+", role_text)
        if len(word) > 2
    }

    if role_text and role_text in title:
        score += 60

    for word in role_words:
        if word in title:
            score += 8
        elif word in description:
            score += 2

    if location:
        location_text = normalize_text(location)

        if location_text in job_location:
            score += 25

        elif location_text in description:
            score += 8

    return score


def rank_jobs(jobs, role: str, location: str = ""):
    scored = []

    for job in jobs:
        relevance = score_job(
            job,
            role=role,
            location=location,
        )

        scored.append(
            (
                relevance,
                job,
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [job for _, job in scored]