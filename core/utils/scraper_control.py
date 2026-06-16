import threading


_STOP_EVENT = threading.Event()


def request_stop():
    _STOP_EVENT.set()


def clear_stop():
    _STOP_EVENT.clear()


def should_stop() -> bool:
    return _STOP_EVENT.is_set()
