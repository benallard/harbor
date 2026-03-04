import time


def start_gc(registry, on_change):

    while True:

        expired = registry.remove_expired()

        if expired:
            on_change()

        time.sleep(5)
