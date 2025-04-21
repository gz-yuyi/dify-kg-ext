import click
import uvicorn


@click.group()
def cli():
    """Knowledge Database CLI Tool"""
    pass


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the API server")
@click.option("--port", default=5001, help="Port to bind the API server")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host, port, reload):
    """Start the knowledge database API server"""
    click.echo(f"Starting API server on {host}:{port}")
    uvicorn.run("dify_kg_ext.entrypoints.api:app", host=host, port=port, reload=reload)


def main():
    cli()


if __name__ == "__main__":
    main()