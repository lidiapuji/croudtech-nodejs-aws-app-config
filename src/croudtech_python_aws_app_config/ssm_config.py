import boto3
import json
import os
import yaml
from collections import MutableMapping
import logging
import re
from click._compat import open_stream
import click
import botocore
import sys
logger = logging.getLogger()
logger.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'INFO')))
handler = logging.StreamHandler(sys.stdout)
# handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def convert_flatten(d, parent_key="", sep="_"):
    items = []
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
        ssm_prefix="/lambda",
        region="eu-west-2",
        include_common=True,
    ):
        self.environment_name = environment_name
        self.app_name = app_name
        self.click = click
        self.ssm_prefix = ssm_prefix
        self.region = region
        self.include_common = include_common

    @property
    def ssm_client(self):
        if not hasattr(self, "_ssm_client"):
            self._ssm_client = boto3.client("ssm", region_name=self.region)
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
        return parameters

    def fetch_parameters(self, path):
        try:
            parameters = {}
            for parameter in self.fetch_paginated_parameters(path):
                parameter_name = parameter["Name"].replace(path, "")
                parameters[parameter_name] = parameter["Value"]
                logger.debug("Fetched parameters from AWS SSM.")
        except botocore.exceptions.ClientError as err:
            logger.debug("Failed to fetch parameters. Invalid token")
            return {}
        except botocore.exceptions.NoCredentialsError as err:
            logger.debug("Failed to fetch parameters. Could not find AWS credentials")
            return {}
        return parameters

    def fetch_paginated_parameters(self, path):
        parameters = []
        fetch_next_page = True
        api_parameters = {"Path": path, "Recursive": True, "WithDecryption": True}
        while fetch_next_page:
            response = self.ssm_client.get_parameters_by_path(
                **api_parameters
            )

            if "Parameters" in response:
                parameters = parameters + response['Parameters']
            if "NextToken" in response:
                api_parameters["NextToken"] = response["NextToken"]
                fetch_next_page = True
            else:
                fetch_next_page = False

        return parameters

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

    def params_to_env(self):
        strings = []
        for parameter, value in self.get_parameters().items():
            env_name = self.parameter_name_to_underscore(parameter)
            os.environ[env_name] = value
            strings.append("%s=%s" % (env_name, value))
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
            contents = contents.decode('utf-8')

        if file_extension == ".yaml":
            data = yaml.load(contents, Loader=yaml.FullLoader)
        elif file_extension == ".json":
            data = json.loads(contents)
        else:
            raise Exception("File format is not valid")

        flattened = convert_flatten(data, sep="/", parent_key=self.ssm_path)
        if delete_first:
            self.delete_existing()

        if encrypted:
            parameter_type = "SecureString"
        else:
            parameter_type = "String"
        for key, value in flattened.items():
            response = self.ssm_client.put_parameter(
                Name=key,
                Description="Created by croudtech lambda helper tool",
                Value=str(value),
                Type=parameter_type,
                Overwrite=True,
                Tier="Intelligent-Tiering",
            )
            self.info("Added %s (encrypted=%s)" % (key, encrypted))

    def info(self, message):
        self.click.echo(message)


class SsmConfigManager:
    def __init__(self, ssm_prefix, region, click, values_path):
        self.ssm_prefix = ssm_prefix
        self.region = region
        self.click = click
        self.values_path = values_path

    @property
    def values_path_real(self):
        return os.path.realpath(self.values_path)

    def put_parameters_recursive(self, delete_first):
        environment_paths = os.listdir(self.values_path_real)
        for environment_name in environment_paths:
            environment_path = os.path.join(self.values_path_real, self.values_path_real, environment_name)
            for file in os.listdir(environment_path):
                file_path = os.path.join(environment_path, file)
                # file_obj = LazyFile(filename=file_path, mode="r")
                file_contents, should_close = open_stream(
                    file_path, 'r', atomic=False
                )
                # print(dir(file_contents))
                # exit()
                matches = re.search('^([^.]+)\.(secret)?', file)
                encrypted = False
                if matches:
                    if matches.group(2) == 'secret':
                        encrypted=True
                    app_name = matches.group(1)
                    ssm_config = SsmConfig(
                        environment_name=environment_name,
                        app_name=app_name,
                        ssm_prefix=self.ssm_prefix,
                        region=self.region,
                        click=self.click,
                    )

                    ssm_config.put_values(file_contents, encrypted, delete_first=delete_first)


        # for root, subdirs, files in os.walk(self.values_path_real):
        #     print(root)
        #     print(subdirs)
        #     print(files)
        # pass
