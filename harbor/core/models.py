from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Service:
    id: str
    kind: str  # "proxy", "static", "sidecar"
    prefix: Optional[str] = None # for "proxy" and "static" services
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
    abilities: List[str] = None # for sidecars


    def from_dict(data: dict, source: str) -> "Service":
        return Service(
            id=data["id"],
            kind=data["kind"],
            prefix=data.get("prefix"),
            upstreams=data.get("upstreams"),
            directory=data.get("directory"),
            source=source,
            public=data.get("public", True),
            public_paths=data.get("public_paths"),
            name=data.get("name"),
            icon=data.get("icon"),
            priority=data.get("priority", False),
            transcoder=data.get("transcoder"),
            sidecars=data.get("sidecars"),
            abilities=data.get("abilities"),
        )


@dataclass
class Lease:
    service_id: str
    token: str
    ttl: int
    expires_at: float
