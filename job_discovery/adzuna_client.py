import os
import httpx

from dotenv import load_dotenv

from .models import JobListing


load_dotenv()


class AdzunaClient:
    BASE_URL = "https://api.adzuna.com/v1/api"

    def __init__(self):
        self.app_id = os.getenv("ADZUNA_APP_ID")
        self.app_key = os.getenv("ADZUNA_APP_KEY")

        if not self.app_id:
            raise RuntimeError("ADZUNA_APP_ID is missing from .env")

        if not self.app_key:
            raise RuntimeError("ADZUNA_APP_KEY is missing from .env")

    def search_jobs(
        self,
        role: str,
        location: str = "",
        page: int = 1,
        results_per_page: int = 20,
    ):
        """
        Search live Adzuna job listings.

        India country code is 'in'.
        """

        url = f"{self.BASE_URL}/jobs/in/search/{page}"

        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": min(results_per_page, 50),
            "what": role,
            "content-type": "application/json",
        }

        if location and location.lower() not in {
            "india",
            "all india",
            "anywhere in india",
        }:
            params["where"] = location

        try:
            response = httpx.get(
                url,
                params=params,
                timeout=20.0,
                follow_redirects=True,
            )

            response.raise_for_status()

            data = response.json()

        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Adzuna API returned HTTP {exc.response.status_code}"
            ) from exc

        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not connect to Adzuna API: {exc}"
            ) from exc

        except ValueError as exc:
            raise RuntimeError(
                "Adzuna returned an invalid JSON response."
            ) from exc

        results = []

        for item in data.get("results", []):
            company = (
                item.get("company", {}).get("display_name")
                or "Company not specified"
            )

            location_data = item.get("location", {})

            job_location = (
                location_data.get("display_name")
                or ", ".join(location_data.get("area", []))
                or "Location not specified"
            )

            category = item.get("category", {})

            results.append(
                JobListing(
                    id=str(item.get("id", "")),
                    title=(item.get("title") or "").strip(),
                    company=company.strip(),
                    location=job_location.strip(),
                    description=(item.get("description") or "").strip(),
                    source="Adzuna",
                    url=(item.get("redirect_url") or "").strip(),
                    created=item.get("created"),
                    contract_type=item.get("contract_type"),
                    contract_time=item.get("contract_time"),
                    category=category.get("label"),
                    salary_min=item.get("salary_min"),
                    salary_max=item.get("salary_max"),
                )
            )

        return {
            "total": data.get("count", len(results)),
            "jobs": results,
        }