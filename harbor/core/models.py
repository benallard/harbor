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
    name: Optional[str] = None  # human-friendly name
    icon: Optional[str] = None  # URL or path to an icon
    priority: bool = False  # if true, this service is displayed with a special highlight
    transcoder: Optional[dict] = None
    bff: Optional[dict] = None

    def from_dict(data: dict, source: str) -> "Service":
        return Service(
            id=data["id"],
            prefix=data["prefix"],
            kind=data["kind"],
            upstreams=data.get("upstreams"),
            directory=data.get("directory"),
            source=source,
            public=data.get("public", True),
            public_paths=data.get("public_paths"),
            name=data.get("name"),
            icon=data.get("icon"),
            priority=data.get("priority", False),
        )


@dataclass
class Lease:
    service_id: str
    token: str
    expires_at: float
    ttl: int
