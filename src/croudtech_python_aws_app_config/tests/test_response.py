# -*- coding: utf-8 -*-

import pytest
import json
from croudtech_python_aws_app_config.response import Response

__author__ = "Jim Robinson"
__copyright__ = "Jim Robinson"

class ValidBodyClass:
    def toString(self):
        return 'Valid Body'

class InvalidBodyClass:
    pass

def test_fib():
    test_body = {
        "Name": "foo",
        "Value": "bar",
    }
    test_body = ValidBodyClass()

    resp = Response(code=200, content_type="json", body=test_body, extra_headers={"X-Trace-Id": "foobar"})
    print(json.dumps(resp.response, indent=2))
    assert False
    # print(resp.response)