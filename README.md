# croudtech-python-aws-app-config

croudtech-python-aws-app-config us a utility to help manage application config using the AWS SSM Parameter Store

There is a cli tool to help set the values and a utility to use the SSM parameters within you application.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install croudtech-python-aws-app-config.

```bash
pip install croudtech-python-aws-app-config
```

## Command Line Usage

```
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

Options:
  --debug / --no-debug
  --endpoint-url TEXT
  --help                Show this message and exit.

Commands:
  delete-parameters
  get-arns
  get-parameters
  put-parameters
  put-parameters-recursive
  manage-redis
```

--endpoint-url specified the AWS API endpoint URL used. This should be used if using localstack or a similar aws mock service. You can also set the `AWS_ENDPOINT_URL` env var to enable this feature.

### Sub Commands

#### delete-parameters

Delete parameters from SSM for a specified app and environment

```
Usage: cli.py delete-parameters [OPTIONS]

Options:
  --environment-name TEXT  The environment name  [required]
  --app-name TEXT          The app name  [required]
  --ssm-prefix TEXT        The ssm path prefix
  --region TEXT            The AWS region
  --help                   Show this message and exit.
```

#### get-arns

Get ARNs for published parameters

```
Usage: cli.py get-arns [OPTIONS]

Options:
  --environment-name TEXT         The environment name  [required]
  --app-name TEXT                 The app name  [required]
  --ssm-prefix TEXT               The ssm path prefix
  --region TEXT                   The AWS region
  --include-common / --ignore-common
                                  Include shared variables
  --output-format [ecs]
  --help                          Show this message and exit.
```

#### get-parameters

Get parameters for a specific app and environment

```
Usage: cli.py get-parameters [OPTIONS]

Options:
  --environment-name TEXT         The environment name  [required]
  --app-name TEXT                 The app name  [required]
  --ssm-prefix TEXT               The ssm path prefix
  --region TEXT                   The AWS region
  --include-common / --ignore-common
                                  Include shared variables
  --output-format [json|yaml|environment|environment-export]
  --help                          Show this message and exit.
```

You can export the variables to your local shell by using

```
eval $(croudtech-app-config get-parameters --app-name myapp --environment-name myenv --output-format environment-export)
```
#### put-parameters

INPUT should be the path to a yaml or json file

```
Usage: cli.py put-parameters [OPTIONS] INPUT

Options:
  --environment-name TEXT  The environment name  [required]
  --app-name TEXT          The app name  [required]
  --ssm-prefix TEXT        The ssm path prefix
  --region TEXT            The AWS region
  --encrypted TEXT         Do you want these parameters to be encrypted?
  --delete-first           Delete the values in this path before pushing
                           (useful for cleanup)

  --help                   Show this message and exit.
```

#### put-parameters-recursive

Recursively put parameters from a directory with the following structure

```
├── EnvironmentName1
│   ├── AppName1.yaml
│   ├── AppName1.secret.yaml
│   ├── AppName2.yaml
│   └──AppName2.secret.yaml
└── EnvironmentName2
    ├── AppName1.yaml
    ├── AppName1.secret.yaml
    ├── AppName2.yaml
    └──AppName2.secret.yaml
```

Files with a *secret.yaml* or *secret.json* suffix will have the parameters encrypted in SSM.

```
Usage: cli.py put-parameters-recursive [OPTIONS] VALUES_PATH

Options:
  --ssm-prefix TEXT  The ssm path prefix
  --region TEXT      The AWS region
  --delete-first     Delete the values in this path before pushing (useful for
                     cleanup)

  --help             Show this message and exit.
```

## Managing Redis DB Allocation

Manage redis DB allocation

### Sub commands

#### allocate-db

```
Usage: python -m croudtech_python_aws_app_config.cli manage-redis allocate-db
           [OPTIONS]

  Allocate a Redis database for a specified application and environment

Options:
  --redis-host TEXT        The redis host  [required]
  --redis-port INTEGER     The redis port  [required]
  --environment-name TEXT  The environment name  [required]
  --app-name TEXT          The application name  [required]
  --help                   Show this message and exit.
```

#### deallocate-db
```
Usage: python -m croudtech_python_aws_app_config.cli manage-redis deallocate-db
           [OPTIONS]

  Remove Redis database allocation for the specified application and
  environment

Options:
  --redis-host TEXT        The redis host  [required]
  --redis-port INTEGER     The redis port  [required]
  --environment-name TEXT  The environment name  [required]
  --app-name TEXT          The application name  [required]
  --help                   Show this message and exit.
```
#### show-db
```
Usage: python -m croudtech_python_aws_app_config.cli manage-redis show-db
           [OPTIONS]

  Show Allocated Redis Database for a specified application

Options:
  --environment-name TEXT         The environment name  [required]
  --app-name TEXT                 The app name  [required]
  --ssm-prefix TEXT               The ssm path prefix
  --region TEXT                   The AWS region
  --include-common / --ignore-common
                                  Include shared variables
  --help                          Show this message and exit.
```
#### show-dbs
```
Usage: python -m croudtech_python_aws_app_config.cli manage-redis show-dbs
           [OPTIONS]

  Show all allocated Redis databases

Options:
  --redis-host TEXT     The redis host  [required]
  --redis-port INTEGER  The redis port  [required]
  --help                Show this message and exit.
```

## Nested file structure and environment variables

Nested values will have their keys flattened when being converted to environment variables. This allows for a simpler structure than just adding all your env vars separately.

For example:

```
SOME_VARIABLE: test
ANOTHER_VAR: 123
SOME_OTHER_VAR: foo
CONNECTIONS:
  POSTGRESS:
    HOST: somehost
    PORT: 1234
    USERNAME: someuser
    PASSWORD: somepass
```

Would translate into the following environment variables:

```
SOME_VARIABLE="test"
ANOTHER_VAR="123"
SOME_OTHER_VAR="foo"
CONNECTIONS_POSTGRESS_HOST="somehost"
CONNECTIONS_POSTGRESS_PORT="1234"
CONNECTIONS_POSTGRESS_USERNAME="someuser"
CONNECTIONS_POSTGRESS_PASSWORD="somepass"
```

## Usage in application code

In the top of your application bootstrap file (or settings.py in django) add:

```
from croudtech_python_aws_app_config.ssm_config import SsmConfig

ssm_config = SsmConfig(
    environment_name=os.environ.get("ENVIRONMENT_NAME"), app_name=os.environ.get("APP_NAME")
)
ssm_config.params_to_env()
```

Make sure your ENVIRONMENT_NAME and APP_NAME env vars are set.

This will pull values from SSM and inject them into your application environment variables.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.


