# JSON Logging for OpenERP v7

Inspired by CampToCamp's `logging_json` module

This addon allows to output of OpenERP logs in JSON.

## Configuration

The json logging is activated with the environment variable
``OPENERP_LOGGING_JSON`` set to ``1``.

In order to have the logs from the start of the server, you should add
``--load=logging_json_v7,web`` flag when starting the server.

## License

MIT