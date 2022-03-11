import boto3
import json
import os
from botocore import endpoint
import yaml
from collections import MutableMapping
import logging
import re
from click._compat import open_stream
import click
import botocore
import sys
from .redis_config import RedisConfig


logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
handler = logging.StreamHandler(sys.stdout)
# handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logging.getLogger("boto3").setLevel(logging.CRITICAL)
logging.getLogger("botocore").setLevel(logging.CRITICAL)
logging.getLogger("s3transfer").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)


def convert_flatten(d, parent_key="", sep="_"):
    items = []
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k

            if isinstance(v, MutableMapping):
                items.extend(convert_flatten(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
    return dict(items)


class Utils:
    @staticmethod
    def chunk_list(data, chunk_size):
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]


class SsmConfig:
    def __init__(
        self,
        environment_name,
        app_name,
        click=click,
        ssm_prefix="/appconfig",
        region="eu-west-2",
        include_common=True,
        use_sns=True,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", None),
        put_metrics=True,
        parse_redis=True
    ):
        self.environment_name = environment_name
        self.app_name = app_name
        self.click = click
        self.ssm_prefix = ssm_prefix
        self.region = region
        self.include_common = include_common
        self.logger = logging.getLogger(self.__class__.__name__)
        self.use_sns = use_sns
        self.endpoint_url = endpoint_url
        self.put_metrics = put_metrics
        self.parse_redis = parse_redis

    @property
    def ssm_client(self):
        if not hasattr(self, "_ssm_client"):
            self._ssm_client = boto3.client(
                "ssm", region_name=self.region, endpoint_url=self.endpoint_url
            )
        return self._ssm_client

    @property
    def ssm_path(self):
        return "%s/%s/%s" % (self.ssm_prefix, self.app_name, self.environment_name)

    @property
    def common_ssm_path(self):
        return "%s/%s/%s" % (self.ssm_prefix, "common", self.environment_name)

    def get_parameters(self):
        if self.include_common:
            parameters = self.fetch_parameters(self.common_ssm_path)
        else:
            parameters = {}

        parameters = {**parameters, **self.fetch_parameters(self.ssm_path)}
        parameters = self.parse_parameters(parameters)
        return parameters

    def parse_parameters(self, parameters):
        if self.parse_redis:
            redis_db, redis_host, redis_port = self.find_redis_config(parameters, allocate=True)
            if redis_db:
                parameters["/REDIS_DB"] = redis_db
                parameters["/REDIS_URL"] = "redis://%s:%s/%s" % (
                    redis_host,
                    redis_port,
                    redis_db,
                )
            else:
                raise Exception("Couldn't allocate Redis Database")
        return parameters
    
    def get_redis_db(self):
        parameters = self.get_parameters()
        redis_db, redis_host, redis_port = self.find_redis_config(parameters)
        return redis_db, redis_host, redis_port

    def find_redis_config(self, parameters, allocate=False):
        if "/REDIS_DB" not in parameters or parameters["/REDIS_DB"] == "auto":
            redis_host = (
                parameters["/REDIS_HOST"] if "/REDIS_HOST" in parameters else False
            )
            redis_port = (
                parameters["/REDIS_PORT"] if "/REDIS_PORT" in parameters else 6379
            )

            if redis_host:
                redis_config_instance = RedisConfig(
                    redis_host=redis_host,
                    redis_port=redis_port,
                    app_name=self.app_name,
                    environment=self.environment_name,
                    put_metrics=self.put_metrics,
                )
                redis_db = redis_config_instance.get_redis_database(allocate)
                return redis_db, redis_host, redis_port
        return None, None, None
    
    @property
    def current_parameters(self):
        if not hasattr(self, "_current_parameters"):
            self._current_parameters = self.fetch_parameters(
                path=self.ssm_path, absolute_path=True
            )
        return self._current_parameters

    def has_changed(self, path, value, encrypted):
        if path not in self.current_parameters:
            return True

        if str(self.current_parameters[path]) != str(value):
            return True
        return False

    def put_parameter(self, path, value, is_abs_path=False, encrypted=False):
        if not is_abs_path:
            key = "%s/%s" % (self.ssm_path, path)
        else:
            key = path

        if encrypted:
            parameter_type = "SecureString"
        else:
            parameter_type = "String"

        value = self.parse_value(value)

        if not self.has_changed(path, value, encrypted):
            log_info = {"action": "No change", "key": key}
            self.logger.info(json.dumps(log_info, indent=2))
            return False
        if len(value) == 0:
            self.logger.info("Skipping %s Empty Parameters are not allowed" % path)
            return False

        parameters = {
            "Name": key,
            "Description": "Created by croudtech appconfig helper tool",
            "Value": str(value),
            "Type": parameter_type,
            "Overwrite": True,
            "Tier": "Intelligent-Tiering",
        }
        # print(parameters)
        try:
            response = self.ssm_client.put_parameter(**parameters)
            if response["Version"] > 1:
                adjective = "Updated"
            else:
                adjective = "Created"
            log_info = {
                "action": adjective,
                "key": key,
                "encrypted": encrypted,
                "tier": response["Tier"],
                "version": response["Version"],
            }

            self.logger.info(json.dumps(log_info, indent=2))
            return response
        except botocore.exceptions.ClientError as err:
            if err.response["Error"]["Code"] == "ValidationException":
                self.logger.error("Validation failed for %s" % key)
                self.logger.error(err)
            return False
        except Exception as err:
            self.logger.error(err)
            return False

    def parse_value(self, value):
        try:
            parsed_value = json.dumps(json.loads(value))
        except:
            parsed_value = value
        return str(parsed_value).strip()

    def parse_fetched_parameter(self, parameter):
        value = parameter['Value']
        if value.startswith('ssm:'):
            valueParameterName = value.replace('ssm:', '')
            encrypted = False
            if valueParameterName.startswith('encrypted:'):
                valueParameterName = valueParameterName.replace('encrypted:')
                encrypted = True
            parameterresponse = self.ssm_client.get_parameter(
                Name = valueParameterName,
                WithDecryption = encrypted
            )
            value = parameterresponse['Parameter']['Value']
        return value

    def fetch_parameters(self, path, absolute_path=False):
        try:
            parameters = {}
            for parameter in self.fetch_paginated_parameters(path):
                if absolute_path:
                    parameter_name = parameter["Name"]
                else:
                    parameter_name = parameter["Name"].replace(path, "")
                parameter_value = self.parse_fetched_parameter(parameter)
                parameters[parameter_name] = parameter_value  
        except botocore.exceptions.ClientError as err:
            logger.debug("Failed to fetch parameters. Invalid token")
            return {}
        except botocore.exceptions.NoCredentialsError as err:
            logger.debug("Failed to fetch parameters. Could not find AWS credentials")
            return {}
        return parameters

    def fetch_paginated_parameters(self, path):
        if not hasattr(self, "fetched_parameters"):
            self.fetched_parameters = {}
        if path not in self.fetched_parameters:
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            parameters = paginator.paginate(
                Path=path,
                Recursive=True,
                WithDecryption=True,    
            )
            
            self.fetched_parameters["path"] = parameters.build_full_result()["Parameters"]
            
            for item in self.fetched_parameters["path"]:
                logger.debug("Found Parameter %s." % item["Name"])
            logger.debug("Fetched parameters from AWS SSM for path %s." % path)
        return self.fetched_parameters["path"]

    def parameter_name_to_underscore(self, name):
        return name[1 : len(name)].replace("/", "_")

    def params_to_nested_dict(self):
        nested = {}
        for parameter, value in self.get_parameters().items():
            parameter_parts = parameter[1 : len(parameter)].split("/")
            current = nested
            for index, part in enumerate(parameter_parts):
                is_leaf = index == (len(parameter_parts) - 1)
                if is_leaf:
                    current[part] = value
                else:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

        return nested

    def arns_for_ecs(self):
        secrets = []
        if self.include_common:
            parameters = self.fetch_paginated_parameters(self.common_ssm_path)
        else:
            parameters = []
        parameters = [*parameters, *self.fetch_paginated_parameters(self.ssm_path)]
        for parameter in parameters:
            short_parameter_name = parameter["Name"].replace(self.common_ssm_path, "")
            short_parameter_name = short_parameter_name.replace(self.ssm_path, "")
            env_name = self.parameter_name_to_underscore(short_parameter_name)
            secrets.append({"Name": env_name, "ValueFrom": parameter["ARN"]})
        return secrets

    def params_to_env(self, export=False):
        strings = []
        for parameter, value in self.get_parameters().items():
            env_name = self.parameter_name_to_underscore(parameter)
            os.environ[env_name] = str(value)
            prefix = "export " if export else ""
            strings.append(
                '%s%s="%s"'
                % (
                    prefix,
                    env_name,
                    str(value).replace("\n", "\\n").replace('"', '\\"'),
                )
            )
            logger.debug("Imported %s from SSM to env var %s" % (parameter, env_name))

        return "\n".join(strings)

    def delete_existing(self):
        parameters = self.get_parameters()
        paths = []

        for key, value in parameters.items():
            paths.append("%s%s" % (self.ssm_path, key))

        if len(paths) == 0:
            return False
        path_chunks = Utils.chunk_list(paths, 10)
        for chunk in path_chunks:
            response = self.ssm_client.delete_parameters(Names=chunk)
            for parameter in response["DeletedParameters"]:
                self.info("Deleted parameter %s" % parameter)
        return True

    def put_values(self, input, encrypted, delete_first):
        filename, file_extension = os.path.splitext(input.name)
        contents = input.read()
        if not isinstance(contents, str):
            contents = contents.decode("utf-8")

        if file_extension == ".yaml":
            data = yaml.load(contents, Loader=yaml.FullLoader)
        elif file_extension == ".json":
            data = json.loads(contents)
        else:
            raise Exception("File format is not valid")

        flattened = convert_flatten(data, sep="/", parent_key=self.ssm_path)
        if delete_first:
            self.delete_existing()

        for key, value in flattened.items():
            self.put_parameter(
                path=key, is_abs_path=True, value=value, encrypted=encrypted
            )

    def info(self, message):
        self.click.echo(message)


class SsmConfigManager:
    def __init__(
        self,
        ssm_prefix,
        region,
        click,
        values_path,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", None),
    ):
        self.ssm_prefix = ssm_prefix
        self.region = region
        self.click = click
        self.values_path = values_path
        self.endpoint_url = endpoint_url

    @property
    def values_path_real(self):
        return os.path.realpath(self.values_path)

    def put_parameters_recursive(self, delete_first):
        environment_paths = os.listdir(self.values_path_real)
        for environment_name in environment_paths:
            environment_path = os.path.join(
                self.values_path_real, self.values_path_real, environment_name
            )
            for file in os.listdir(environment_path):
                file_path = os.path.join(environment_path, file)
                file_contents, should_close = open_stream(file_path, "r", atomic=False)
                matches = re.search("^([^.]+)\.(secret)?", file)
                encrypted = False
                if matches:
                    if matches.group(2) == "secret":
                        encrypted = True
                    app_name = matches.group(1)
                    ssm_config = SsmConfig(
                        environment_name=environment_name,
                        app_name=app_name,
                        ssm_prefix=self.ssm_prefix,
                        region=self.region,
                        click=self.click,
                        endpoint_url=self.endpoint_url,
                    )

                    ssm_config.put_values(
                        file_contents, encrypted, delete_first=delete_first
                    )
