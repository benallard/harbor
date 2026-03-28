from harbor.core.models import Service


class ProxyBackend:

    def apply(self, services):
        """
        Apply the whole configuration.
        Meant to be called at startup whenthe static configuration is loaded.
        """
        raise NotImplementedError

    def register(self, service: Service):
        """
        Register a new service.
        Meant to be called when a service is added over the API.
        """
        raise NotImplementedError

    def unregister(self, service: Service):
        """
        Unregister a service.
        Meant to be called when a service is removed over the API, or its lease expires.
        """
        raise NotImplementedError

    @property
    def listener_url(self) -> str:
        """
        Get the URL of the backend's listener.
        This is used for delegation — services of delegated kinds are transformed into proxies to this URL.
        """
        raise NotImplementedError
