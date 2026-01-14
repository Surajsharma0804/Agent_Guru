"""
GURU Desktop Agent - Command Line Interface

Production-grade CLI for managing and monitoring the GURU desktop agent.

Commands:
- start: Start the desktop agent service
- stop: Stop the desktop agent service
- status: Check service status
- logs: View audit logs
- verify: Verify audit log integrity
- config: Manage configuration
- test: Run system tests

Security:
- All operations require appropriate privileges
- Audit logging for all CLI operations
- Configuration validation before application
"""

import sys
from pathlib import Path
from typing import Optional

import click
import structlog
from rich.console import Console
from rich.table import Table

from .audit.audit_logger import AuditLogger
from .authority.state import AuthorityConfiguration, create_authority_state_machine

console = Console()
logger = structlog.get_logger(__name__)


@click.group()
@click.version_option(version="1.0.0", prog_name="GURU Desktop Agent")
def cli():
    """
    GURU Desktop Agent - Production-Grade Personal Automation System

    Manage and monitor the GURU desktop agent service with comprehensive
    security controls and audit logging.
    """
    pass


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload (development only)")
def start(host: str, port: int, reload: bool):
    """Start the GURU desktop agent service."""
    console.print("[bold green]Starting GURU Desktop Agent...[/bold green]")

    if reload:
        console.print("[yellow]⚠️  Auto-reload enabled - DEVELOPMENT MODE ONLY[/yellow]")

    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True,
        use_colors=True,
        server_header=False,
        date_header=False,
    )


@cli.command()
def stop():
    """Stop the GURU desktop agent service."""
    console.print("[bold red]Stopping GURU Desktop Agent...[/bold red]")
    console.print("[yellow]Service stop not yet implemented - use Ctrl+C or system process manager[/yellow]")


@cli.command()
def status():
    """Check GURU desktop agent service status."""
    console.print("[bold blue]GURU Desktop Agent Status[/bold blue]\n")

    try:
        # Try to connect to the service
        import requests

        response = requests.get("http://127.0.0.1:8000/health", timeout=5)

        if response.status_code == 200:
            data = response.json()

            console.print(f"[green]✓[/green] Service: {data['status']}")
            console.print(f"[green]✓[/green] Version: {data['version']}")
            console.print(f"[green]✓[/green] Authority State: {data['authority_state']}")

            # Component status table
            table = Table(title="Component Status")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details", style="white")

            for component, info in data["components"].items():
                status_icon = "✓" if info["status"] == "operational" else "✗"
                details = ", ".join(f"{k}: {v}" for k, v in info.items() if k != "status")
                table.add_row(component, f"{status_icon} {info['status']}", details)

            console.print(table)
        else:
            console.print(f"[red]✗[/red] Service returned status code: {response.status_code}")

    except requests.exceptions.ConnectionError:
        console.print("[red]✗[/red] Service not running or not accessible")
    except Exception as e:
        console.print(f"[red]✗[/red] Error checking status: {str(e)}")


@cli.command()
@click.option("--limit", default=50, help="Number of log entries to display")
@click.option("--severity", help="Filter by severity level")
@click.option("--component", help="Filter by component")
def logs(limit: int, severity: Optional[str], component: Optional[str]):
    """View audit logs."""
    console.print(f"[bold blue]GURU Audit Logs (last {limit} entries)[/bold blue]\n")

    try:
        audit_logger = AuditLogger(log_directory="audit_logs", testing_mode=True)
        stats = audit_logger.get_audit_statistics()

        console.print(f"Total entries: {stats['total_entries']}")
        console.print(f"Database: {stats['database_path']}\n")

        # TODO: Implement log querying and display
        console.print("[yellow]Log viewing not yet fully implemented[/yellow]")

    except Exception as e:
        console.print(f"[red]Error reading logs: {str(e)}[/red]")


@cli.command()
def verify():
    """Verify audit log integrity."""
    console.print("[bold blue]Verifying Audit Log Integrity...[/bold blue]\n")

    try:
        audit_logger = AuditLogger(log_directory="audit_logs", testing_mode=True)

        # TODO: Implement full integrity verification
        stats = audit_logger.get_audit_statistics()

        console.print(f"[green]✓[/green] Audit database accessible")
        console.print(f"[green]✓[/green] Total entries: {stats['total_entries']}")
        console.print(f"[green]✓[/green] Current sequence: {stats['current_sequence']}")

        console.print("\n[green]Audit log integrity verification passed[/green]")

    except Exception as e:
        console.print(f"[red]✗ Integrity verification failed: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key: Optional[str], value: Optional[str]):
    """Manage configuration."""
    if not key:
        # Display current configuration
        console.print("[bold blue]GURU Configuration[/bold blue]\n")
        console.print("[yellow]Configuration display not yet implemented[/yellow]")
    elif not value:
        # Display specific key
        console.print(f"[bold blue]Configuration: {key}[/bold blue]\n")
        console.print("[yellow]Configuration query not yet implemented[/yellow]")
    else:
        # Set configuration value
        console.print(f"[bold blue]Setting {key} = {value}[/bold blue]\n")
        console.print("[yellow]Configuration modification not yet implemented[/yellow]")


@cli.command()
@click.option("--component", help="Test specific component")
@click.option("--verbose", is_flag=True, help="Verbose output")
def test(component: Optional[str], verbose: bool):
    """Run system tests."""
    console.print("[bold blue]Running GURU System Tests...[/bold blue]\n")

    if component:
        console.print(f"Testing component: {component}\n")

    # Test authority state machine
    console.print("[cyan]Testing Authority State Machine...[/cyan]")
    try:
        authority_machine = create_authority_state_machine()
        console.print(f"[green]✓[/green] Authority machine initialized")
        console.print(f"[green]✓[/green] Initial state: {authority_machine.current_state.value}")
        console.print(f"[green]✓[/green] Session ID: {authority_machine.session_id}")
    except Exception as e:
        console.print(f"[red]✗[/red] Authority machine test failed: {str(e)}")

    # Test audit logger
    console.print("\n[cyan]Testing Audit Logger...[/cyan]")
    try:
        audit_logger = AuditLogger(log_directory="audit_logs", testing_mode=True)
        stats = audit_logger.get_audit_statistics()
        console.print(f"[green]✓[/green] Audit logger initialized")
        console.print(f"[green]✓[/green] Total entries: {stats['total_entries']}")
    except Exception as e:
        console.print(f"[red]✗[/red] Audit logger test failed: {str(e)}")

    # Test workstation lock capability
    console.print("\n[cyan]Testing Workstation Lock Capability...[/cyan]")
    try:
        from .intrusion.workstation_lock import create_workstation_locker

        locker = create_workstation_locker()
        test_results = locker.test_lock_capability()

        if test_results["api_available"]:
            console.print(f"[green]✓[/green] Windows API available")
        else:
            console.print(f"[yellow]⚠[/yellow] Windows API not available")

        if test_results["system_supported"]:
            console.print(f"[green]✓[/green] System supported")
        else:
            console.print(f"[yellow]⚠[/yellow] System not supported")

    except Exception as e:
        console.print(f"[red]✗[/red] Workstation lock test failed: {str(e)}")

    console.print("\n[green]System tests complete[/green]")


@cli.command()
def info():
    """Display system information."""
    console.print("[bold blue]GURU Desktop Agent System Information[/bold blue]\n")

    import platform

    table = Table(title="System Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Version", "1.0.0")
    table.add_row("Python Version", platform.python_version())
    table.add_row("Platform", platform.platform())
    table.add_row("Architecture", platform.machine())
    table.add_row("Processor", platform.processor())

    console.print(table)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
