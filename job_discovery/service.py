from .adzuna_client import AdzunaClient
from .job_filter import (
    deduplicate_jobs,
    is_valid_job,
    rank_jobs,
)


class JobDiscoveryService:

    MAX_RESULTS = 20

    def __init__(self):
        self.client = AdzunaClient()

    def find_jobs(
        self,
        role: str,
        location: str = "",
        experience: str = "",
    ):
        role = (role or "").strip()
        location = (location or "").strip()
        experience = (experience or "").strip()

        if not role:
            raise ValueError("Job role is required.")

        # Request more than 10 so filtering still leaves enough results.
        api_result = self.client.search_jobs(
            role=role,
            location=location,
            page=1,
            results_per_page=50,
        )

        jobs = api_result["jobs"]

        # Remove unusable listings.
        jobs = [
            job
            for job in jobs
            if is_valid_job(job)
        ]

        # Remove duplicates.
        jobs = deduplicate_jobs(jobs)

        # Rank according to role/location relevance.
        jobs = rank_jobs(
            jobs,
            role=role,
            location=location,
        )

        # Maximum 10.
        jobs = jobs[: self.MAX_RESULTS]

        return {
            "success": True,
            "role": role,
            "location": location,
            "experience": experience,
            "total_found": api_result["total"],
            "returned": len(jobs),
            "jobs": [
                job.to_dict()
                for job in jobs
            ],
        }