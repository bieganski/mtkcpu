from colorlog import ColoredFormatter


_log = None


def get_color_logging_object():
    global _log
    if _log is not None:
        return _log

    import logging

    LOG_LEVEL = logging.DEBUG
    LOGFORMAT = (
        "  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
    )

    logging.root.setLevel(LOG_LEVEL)
    formatter = ColoredFormatter(LOGFORMAT)
    stream = logging.StreamHandler()
    stream.setLevel(LOG_LEVEL)
    stream.setFormatter(formatter)
    log = logging.getLogger("pythonConfig")
    log.setLevel(LOG_LEVEL)
    log.addHandler(stream)

    _log = log

    return _log

def get_members(arg) -> str:
    from inspect import getmembers
    from pprint import pformat
    return pformat(getmembers(arg))
