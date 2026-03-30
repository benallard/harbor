from .app import create_app
from .core.config import load_config

_config = load_config()
app = create_app(_config)
