
import logging
import os
import threading
import time

from distutils.util import strtobool
from openerp.sql_db import Cursor
from openerp.addons.web.http import WebRequest
from openerp.service import wsgi_server
from werkzeug.urls import uri_to_iri

_logger = logging.getLogger(__name__)
TIMING_DP = 6

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None  # noqa
    _logger.debug("Cannot 'import pythonjsonlogger'.")


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


class OdooJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        record.pid = os.getpid()
        record.dbname = getattr(threading.currentThread(), 'dbname', '?')
        _super = super(OdooJsonFormatter, self)
        return _super.add_fields(log_record, record, message_dict)


class JsonPerfFilter(logging.Filter):
    def filter(self, record):
        if hasattr(threading.current_thread(), "query_count"):
            record.response_time = round(
                time.time() - threading.current_thread().perf_t0, TIMING_DP)
            record.query_count = threading.current_thread().query_count
            record.query_time = round(
                threading.current_thread().query_time, TIMING_DP)
            delattr(threading.current_thread(), "query_count")
        return True

if is_true(os.environ.get('OPENERP_LOGGING_JSON')):

    # Replace odoo default log formatter
    format = ('%(asctime)s %(pid)s %(levelname)s'
              '%(dbname)s %(name)s: %(message)s')
    formatter = OdooJsonFormatter(format)
    logging.getLogger().handlers[0].formatter = formatter

    # Monkey-patch sql performance logging into Cursor
    execute_orig = Cursor.execute
    def execute(*args, **kwargs):
        current_thread = threading.current_thread()
        if not getattr(current_thread, 'query_count', False):
            current_thread.query_count = 0
            current_thread.query_time = 0
        start = time.time()
        res = execute_orig(*args, **kwargs)
        current_thread.query_count += 1
        current_thread.query_time += (time.time() - start)
        return res
    Cursor.execute = execute

    http_logger = logging.getLogger('werkzeug')

    # Configure performance logging
    json_perf_filter = JsonPerfFilter()
    http_logger.addFilter(json_perf_filter)

    # define http log_request method
    def log_request(self, code="-", size="-"):
        try:
            path = uri_to_iri(self.path)
        except AttributeError:
            # path isn't set if the requestline was bad
            path = self.requestline
        record = {
            "method": self.command,
            "path": path,
            "http_ver": self.request_version,
            "http_code": str(code),
            "size": size,
            "client_addr": self.address_string()
        }
        http_logger.info('request%s', '', extra=record)

    # Patch WebRequest class to customise logging and track request start time
    log_request_patched = False
    init_orig = WebRequest.init
    def init(*args, **kwargs):
        global log_request_patched
        if not log_request_patched:
            wsgi_server.httpd.RequestHandlerClass.log_request = log_request
            log_request_patched = True
        threading.current_thread().perf_t0 = time.time()
        return init_orig(*args, **kwargs)
    WebRequest.init = init
