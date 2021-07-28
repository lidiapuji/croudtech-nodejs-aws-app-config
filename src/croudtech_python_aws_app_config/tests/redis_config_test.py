# -*- coding: utf-8 -*-

import pytest
import json
from croudtech_python_aws_app_config.redis_config import RedisConfig

__author__ = "Jim Robinson"
__copyright__ = "Jim Robinson"


def test_redis_config():
    redis_config_instance = RedisConfig(
        redis_host="127.0.0.1", redis_port=6379, app_name="test_app", environment="test"
    )

    redis_database = redis_config_instance.get_redis_database()
    assert redis_database == 0

    redis_config_instance = RedisConfig(
        redis_host="127.0.0.1", redis_port=6379, app_name="test_app", environment="test"
    )

    redis_database = redis_config_instance.get_redis_database()
    assert redis_database == 0

    redis_config_instance = RedisConfig(
        redis_host="127.0.0.1",
        redis_port=6379,
        app_name="test_app2",
        environment="test",
    )

    redis_database = redis_config_instance.get_redis_database()
    assert redis_database == 1
