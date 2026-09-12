import logging
import sys


class CorrelationFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "missing"

        return True


logger = logging.getLogger("relay")

logger.setLevel(logging.INFO)


handler = logging.StreamHandler(sys.stdout)


formatter = logging.Formatter(
    "%(asctime)s "
    "%(levelname)s "
    "correlation_id=%(correlation_id)s "
    "%(message)s"
)


handler.setFormatter(formatter)
handler.addFilter(CorrelationFilter())


logger.addHandler(handler)