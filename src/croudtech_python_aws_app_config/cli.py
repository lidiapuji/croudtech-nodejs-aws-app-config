import json
from botocore import endpoint
import click
import os
from pathlib import Path
import collections
from .ssm_config import SsmConfig, SsmConfigManager
from yaml import load, dump
from .redis_config import RedisConfig


try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def object2table(object):
    col1width = len(max(object.keys(), key=len))
    col2width = len(str(max(object.values())))
    headfoot = "+-%s-+-%s-+" % ("-" * col1width, "-" * col2width)
    lines = [
       headfoot
    ]
    for k, v in object.items():
        col1pad = " " * (col1width - len(str(k)))
        col2pad = " " * (col2width - len(str(v)))
        lines.append('| %s%s | %s%s |' % (k, col1pad, v, col2pad))
    lines.append(headfoot)
    return "\n".join(lines)

@click.group()
@click.option(
    "--endpoint-url",
    default=os.getenv("AWS_ENDPOINT_URL", None),
    help="The AWS API endpoint URL",
)
@click.option(
    "--put-metrics",
    default=True,
    help="Use Cloudwatch Metrics to track usage",
)
@click.pass_context
def cli(ctx, endpoint_url, put_metrics):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    ctx.obj["AWS_ENDPOINT_URL"] = endpoint_url
    if ctx.obj["AWS_ENDPOINT_URL"]:
        click.echo(
            click.style(
                "Using aws endpoint url %s" % ctx.obj["AWS_ENDPOINT_URL"],
                blink=True,
                bold=True,
            )
        )

    ctx.obj["PUT_METRICS"] = put_metrics


@cli.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/appconfig", help="The ssm path prefix")
@click.option("--region", default="eu-west-2", help="The AWS region")
@click.option(
    "--include-common/--ignore-common",
    default=True,
    is_flag=True,
    help="Include shared variables",
)
@click.option(
    "--output-format",
    default="json",
    type=click.Choice(["json", "yaml", "environment", "environment-export"]),
)
@click.option(
    "--parse-redis-param/--ignore-redis-param",
    default=True,
    is_flag=True,
    help="Parse redis host and allocate a redis database number"
)
def get_parameters(
    ctx, environment_name, app_name, ssm_prefix, region, include_common, output_format, parse_redis_param
):
    ssm_config = SsmConfig(
        environment_name=environment_name,
        app_name=app_name,
        ssm_prefix=ssm_prefix,
        region=region,
        include_common=include_common,
        click=click,
        endpoint_url=ctx.obj["AWS_ENDPOINT_URL"],
        put_metrics=ctx.obj["PUT_METRICS"],
        parse_redis=parse_redis_param
    )
    output = "Invalid output format"

    if output_format == "json":
        output = json.dumps(ssm_config.params_to_nested_dict(), indent=2)
    elif output_format == "yaml":
        output = dump(ssm_config.params_to_nested_dict(), Dumper=Dumper)
    elif output_format == "environment":
        output = ssm_config.params_to_env()
    elif output_format == "environment-export":
        output = ssm_config.params_to_env(export=True)

    if isinstance(output, str):
        print(output)


@cli.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/appconfig", help="The ssm path prefix")
@click.option("--region", default="eu-west-2", help="The AWS region")
@click.option(
    "--include-common/--ignore-common",
    default=True,
    is_flag=True,
    help="Include shared variables",
)
@click.option("--output-format", default="ecs", type=click.Choice(["ecs"]))
def get_arns(
    ctx, environment_name, app_name, ssm_prefix, region, include_common, output_format
):
    ssm_config = SsmConfig(
        environment_name=environment_name,
        app_name=app_name,
        ssm_prefix=ssm_prefix,
        region=region,
        include_common=include_common,
        click=click,
        endpoint_url=ctx.obj["AWS_ENDPOINT_URL"],
        put_metrics=ctx.obj["PUT_METRICS"],
    )
    output = "Invalid output format"

    if output_format == "ecs":
        output = dump(ssm_config.arns_for_ecs(), indent=2)

    if isinstance(output, str):
        print(output)


@cli.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/appconfig", help="The ssm path prefix")
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
        endpoint_url=ctx.obj["AWS_ENDPOINT_URL"],
        put_metrics=ctx.obj["PUT_METRICS"],
    )

    ssm_config.put_values(input, encrypted, delete_first=delete_first)


@cli.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/appconfig", help="The ssm path prefix")
@click.option("--region", default="eu-west-2", help="The AWS region")
def delete_parameters(ctx, environment_name, app_name, ssm_prefix, region):
    ssm_config = SsmConfig(
        environment_name=environment_name,
        app_name=app_name,
        ssm_prefix=ssm_prefix,
        region=region,
        click=click,
        endpoint_url=ctx.obj["AWS_ENDPOINT_URL"],
        put_metrics=ctx.obj["PUT_METRICS"],
    )

    ssm_config.delete_existing()


@cli.command()
@click.pass_context
@click.option("--ssm-prefix", default="/appconfig", help="The ssm path prefix")
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
        ssm_prefix=ssm_prefix,
        region=region,
        click=click,
        values_path=values_path,
        endpoint_url=ctx.obj["AWS_ENDPOINT_URL"],
    )

    ssm_config_manager.put_parameters_recursive(delete_first=delete_first)

@cli.group()
def manage_redis():
    """Redis DB Allocation Management"""
    pass

@manage_redis.command()
@click.pass_context
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The app name", required=True)
@click.option("--ssm-prefix", default="/appconfig", help="The ssm path prefix")
@click.option("--region", default="eu-west-2", help="The AWS region")
@click.option(
    "--include-common/--ignore-common",
    default=True,
    is_flag=True,
    help="Include shared variables",
)
def show_db(ctx, environment_name, app_name, ssm_prefix, region, include_common):
    """Show Allocated Redis Database for a specified application"""
    ssm_config = SsmConfig(
        environment_name=environment_name,
        app_name=app_name,
        ssm_prefix=ssm_prefix,
        region=region,
        include_common=include_common,
        click=click,
        endpoint_url=ctx.obj["AWS_ENDPOINT_URL"],
        put_metrics=False,
        parse_redis=False
    )
    redis_db, redis_host, redis_port = ssm_config.get_redis_db()
    click.echo("Redis config: Db: %s, Host: %s, Port: %s" % (redis_db, redis_host, redis_port))

@manage_redis.command()
@click.pass_context
@click.option("--redis-host", help="The redis host", required=True)
@click.option("--redis-port", help="The redis port", required=True, default=6379)
def show_dbs(ctx, redis_host, redis_port):
    """Show all allocated Redis databases"""
    redis_config_instance = RedisConfig(
        redis_host=redis_host,
        redis_port=redis_port,
        app_name="Undefined",
        environment="Undefined",
        put_metrics=False,
    )
    click.secho(object2table(redis_config_instance.redis_db_allocations), fg='cyan')
    
@manage_redis.command()
@click.pass_context
@click.option("--redis-host", help="The redis host", required=True)
@click.option("--redis-port", help="The redis port", required=True, default=6379)
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The application name", required=True)
def allocate_db(ctx, redis_host, redis_port, environment_name, app_name):
    """Allocate a Redis database for a specified application and environment"""
    redis_config_instance = RedisConfig(
        redis_host=redis_host,
        redis_port=redis_port,
        app_name=app_name,
        environment=environment_name,
        put_metrics=False,
    )
    db = redis_config_instance.allocate_db()
    click.secho("Allocated Database %s to %s/%s" % (db, environment_name, app_name), fg='green')
    click.secho(object2table(redis_config_instance.redis_db_allocations), fg="cyan")


@manage_redis.command()
@click.pass_context
@click.option("--redis-host", help="The redis host", required=True)
@click.option("--redis-port", help="The redis port", required=True, default=6379)
@click.option("--environment-name", help="The environment name", required=True)
@click.option("--app-name", help="The application name", required=True)
def deallocate_db(ctx, redis_host, redis_port, environment_name, app_name):
    """Remove Redis database allocation for the specified application and environment"""
    redis_config_instance = RedisConfig(
        redis_host=redis_host,
        redis_port=redis_port,
        app_name=app_name,
        environment=environment_name,
        put_metrics=False,
    )
    success, db = redis_config_instance.deallocate_db()
    if success:
        click.secho("DeAllocated Database %s from %s/%s" % (db, environment_name, app_name), fg="green")
        click.secho("Allocated Databases:", fg="white")
        click.secho(object2table(redis_config_instance.redis_db_allocations), fg="cyan")
    else:
        click.secho("No Database was allocated to %s/%s" % (environment_name, app_name), fg="red", bold=True) 
        click.secho("Allocated Databases:", fg="white")
        click.secho(object2table(redis_config_instance.redis_db_allocations), fg="cyan")

        

if __name__ == "__main__":
    cli()
