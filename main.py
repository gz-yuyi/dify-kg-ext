import click
import uvicorn
import subprocess
import sys


@click.group()
def cli():
    """Knowledge Database CLI Tool"""
    pass


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
    uvicorn.run("dify_kg_ext.entrypoints.api:app", host=host, port=port, reload=reload)


@cli.command()
@click.option("--concurrency", default=4, help="Number of worker processes")
@click.option("--loglevel", default="info", help="Log level (debug, info, warning, error)")
@click.option("--queues", default="celery", help="Comma separated list of queues to listen on")
@click.option("--hostname", default="worker1@%h", help="Custom hostname for worker identification")
def worker(concurrency, loglevel, queues, hostname):
    """Start the Celery worker for document processing"""
    click.echo(f"Starting Celery worker with {concurrency} processes")
    
    # Build Celery command
    cmd = [
        "celery",
        "-A", "dify_kg_ext.entrypoints.worker",
        "worker",
        f"--concurrency={concurrency}",
        f"--loglevel={loglevel}",
        f"--queues={queues}",
        f"--hostname={hostname}"
    ]
    
    # Execute the command
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"Worker failed with error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nWorker stopped by user")


def main():
    cli()


if __name__ == "__main__":
    main()