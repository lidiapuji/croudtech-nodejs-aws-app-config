from http_constants.header import HttpHeaders
from http_constants import status
import json


class Response:
    def __init__(self, code, body, content_type="text", extra_headers={}):
        self._code = code
        self._content_type_name = content_type
        self._body_raw = body
        self._extra_headers = extra_headers
        self.body = self.parse_body()

    @property
    def http_status(self):
        if not hasattr(self, "_http_status"):
            self._http_status = status.HttpStatus(self._code)
        return self._http_status

    @property
    def response(self):
        if not hasattr(self, "_response"):
            self._response = {
                "statusCode": self.http_status.get_code(),
                "statusDescription": str(self.http_status),
                "body": self.body,
                "isBase64Encoded": False,
                "headers": self.headers,
            }
        return self._response

    @property
    def headers(self):
        if not hasattr(self, "_headers"):
            self._headers = dict(
                **{"Content-Type": HttpHeaders.CONTENT_TYPE_VALUES.json},
                **self._extra_headers
            )
        return self._headers

    @property
    def content_type(self):
        if not hasattr(self, "_content_type"):
            self._content_type = getattr(
                HttpHeaders.CONTENT_TYPE_VALUES, self._content_type_name
            )
        return self._content_type

    def parse_body(self):
        if type(self._body_raw) in [dict, list, tuple]:
            self._content_type = HttpHeaders.CONTENT_TYPE_VALUES.json
            return json.dumps(self._body_raw)
        elif hasattr(self._body_raw, "toString"):
            return self._body_raw.toString()
        elif type(self._body_raw) == str:
            return self._body_raw
        else:
            raise Exception(
                "Invalid response body. Must be one of dict, list, tuple, str of implement the toString() method"
            )
