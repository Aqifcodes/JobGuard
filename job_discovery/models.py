from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class JobListing:
    id: str
    title: str
    company: str
    location: str
    description: str
    source: str
    url: str
    created: Optional[str] = None
    contract_type: Optional[str] = None
    contract_time: Optional[str] = None
    category: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None

    def to_dict(self):
        return asdict(self)