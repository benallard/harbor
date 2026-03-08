class ProxyBackend:

    def apply(self, services):
        """
        Apply the whole configuration.
        Meant to be called at startup whenthe static configuration is loaded.
        """
        raise NotImplementedError

    def register(self, service):
        """
        Register a new service.
        Meant to be called when a service is added over the API.
        """
        raise NotImplementedError

    def unregister(self, service):
        """
        Unregister a service.
        Meant to be called when a service is removed over the API, or its lease expires.
        """
        raise NotImplementedError
