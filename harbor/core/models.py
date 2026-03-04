from dataclasses import dataclass
from typing import List, Optional
import time


@dataclass
class Service:
    id: str
    prefix: str
    kind: str
    upstreams: Optional[List[str]] = None
    directory: Optional[str] = None

    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None

    source: str = "file"   # file | dynamic


@dataclass
class Lease:
    service_id: str
    token: str
    expires_at: float
    ttl: int