import json
import click
import os
from pathlib import Path
import collections
from .ssm_config import SsmConfig, SsmConfigManager
from yaml import load, dump

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    ctx.obj["DEBUG"] = debug


@cli.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/lambda", help="The app name")
@click.option("--region", default="eu-west-2", help="The AWS region")
@click.option(
    "--ignore-common", default=True, is_flag=True, help="Include shared variables"
)
@click.option("--output-format", default="json", type=click.Choice(['json', 'yaml', 'environment']))
def get_parameters(
    ctx, environment_name, app_name, ssm_prefix, region, ignore_common, output_format
):
    ssm_config = SsmConfig(
        environment_name=environment_name,
        app_name=app_name,
        ssm_prefix=ssm_prefix,
        region=region,
        include_common=ignore_common,
        click=click,
    )
    output = "Invalid output format"

    if output_format == "json":
        output = json.dumps(ssm_config.params_to_nested_dict(), indent=2)
    elif output_format == "yaml":
        output = dump(ssm_config.params_to_nested_dict(), Dumper=Dumper)
    elif output_format == "environment":
        output = ssm_config.params_to_env()

    if isinstance(output, str):
        print(output)


@cli.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/lambda", help="The app name")
@click.option("--region", default="eu-west-2", help="The AWS region")
@click.option(
    "--encrypted", default=True, help="Do you want this parameter to be encrypted?"
)
@click.option(
    "--delete-first",
    is_flag=True,
    default=False,
    help="Delete the values in this path before pushing (useful for cleanup)",
)
@click.argument("input", type=click.File("rb"))
def put_parameters(
    ctx, environment_name, app_name, ssm_prefix, region, encrypted, input, delete_first
):
    ssm_config = SsmConfig(
        environment_name=environment_name,
        app_name=app_name,
        ssm_prefix=ssm_prefix,
        region=region,
        click=click,
    )

    ssm_config.put_values(input, encrypted, delete_first=delete_first)


@cli.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/lambda", help="The app name")
@click.option("--region", default="eu-west-2", help="The AWS region")
def delete_parameters(ctx, environment_name, app_name, ssm_prefix, region):
    ssm_config = SsmConfig(
        environment_name=environment_name,
        app_name=app_name,
        ssm_prefix=ssm_prefix,
        region=region,
        click=click,
    )

    ssm_config.delete_existing()


@cli.command()
@click.pass_context
@click.option("--ssm-prefix", default="/lambda", help="The app name")
@click.option("--region", default="eu-west-2", help="The AWS region")
@click.option(
    "--delete-first",
    is_flag=True,
    default=False,
    help="Delete the values in this path before pushing (useful for cleanup)",
)
@click.argument("values_path")
def put_parameters_recursive(ctx, ssm_prefix, region, delete_first, values_path):
    ssm_config_manager = SsmConfigManager(
        ssm_prefix=ssm_prefix, region=region, click=click, values_path=values_path
    )

    ssm_config_manager.put_parameters_recursive(delete_first=delete_first)


if __name__ == "__main__":
    cli()
