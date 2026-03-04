class Router:

    def __init__(self):
        self.routes = []

    def rebuild(self, services):

        # longest prefix first
        self.routes = sorted(services, key=lambda s: len(s.prefix), reverse=True)

    def match(self, path):

        for service in self.routes:

            prefix = service.prefix.rstrip("/")

            if path == prefix:
                return service, ""

            if path.startswith(prefix + "/"):
                subpath = path[len(prefix) + 1 :]
                return service, subpath

        return None, None
