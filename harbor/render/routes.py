def render_routes(services):

    routes = []

    for s in services:

        if s.kind == "proxy":

            routes.append(
                {
                    "match": [{"path": [f"{s.prefix}*"]}],
                    "handle": [
                        {
                            "handler": "reverse_proxy",
                            "upstreams": [{"dial": u} for u in s.upstreams],
                        }
                    ],
                }
            )

    return routes
