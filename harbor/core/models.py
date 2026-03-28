from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Service:
    id: str
    prefix: str
    kind: str  # "proxy", "static", "sidecar"
    upstreams: Optional[List[str]] = None
    directory: Optional[str] = None
    source: str = "file"
    public: bool = True
    public_paths: Optional[List[str]] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    priority: bool = False
    transcoder: Optional[dict] = None
    sidecars: Optional[List[str]] = None  # list of sidecar ids
    abilities: List[str]


@dataclass
class Lease:
    service_id: str
    token: str
    ttl: int
    expires_at: float
