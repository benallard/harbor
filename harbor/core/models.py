from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Service:
    id: str
    prefix: str
    kind: str  # "proxy" or "static"
    upstreams: Optional[List[str]] = None
    directory: Optional[str] = None
    source: str = "file"  # "file" vs "dynamic"
    public: bool = True  # included in /catalog
    public_paths: Optional[List[str]] = None  # only these paths are proxied publicly


@dataclass
class Lease:
    service_id: str
    token: str
    expires_at: float
    ttl: int
