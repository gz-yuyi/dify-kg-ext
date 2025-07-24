import click
import uvicorn


@click.group()
def cli():
    """Knowledge Database CLI Tool"""


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind the API server")
@click.option("--port", default=5001, help="Port to bind the API server")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host, port, reload):
    """Start the knowledge database API server with Dify integration

    This server provides:
    - Knowledge Management API (CRUD operations)
    - Dify External Knowledge API (/retrieval endpoint)
    - Health check and documentation
    """
    click.echo(f"Starting Knowledge Database API server on {host}:{port}")
    click.echo("Features:")
    click.echo("  ✅ Knowledge Management API")
    click.echo("  ✅ Dify External Knowledge API")
    click.echo("  ✅ Semantic Search & Vector Retrieval")
    click.echo("")
    click.echo(f"📖 API Documentation: http://{host}:{port}/docs")
    click.echo(f"🏥 Health Check: http://{host}:{port}/health")
    click.echo(f"🤖 Dify Retrieval Endpoint: http://{host}:{port}/retrieval")
    click.echo("")
    click.echo("Configure Dify External Knowledge:")
    click.echo(f"  API Endpoint: http://{host}:{port}/retrieval")
    click.echo("  API Key: Any string longer than 10 characters")
    uvicorn.run("dify_kg_ext.api:app", host=host, port=port, reload=reload)


def main():
    cli()


if __name__ == "__main__":
    main()
