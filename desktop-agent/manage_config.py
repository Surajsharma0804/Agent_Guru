"""
Configuration Management CLI

Command-line interface for managing GURU configuration with:
- View current configuration
- Update configuration values
- Reset configuration to defaults
- Export/import configuration
- List and restore backups
- Auto-detect Ollama models

Usage:
    python manage_config.py view                    # View current configuration
    python manage_config.py set <key> <value>       # Set configuration value
    python manage_config.py reset [--level user]    # Reset configuration
    python manage_config.py export <file>           # Export configuration
    python manage_config.py import <file>           # Import configuration
    python manage_config.py backups                 # List backups
    python manage_config.py restore <backup>        # Restore backup
    python manage_config.py ollama                  # Auto-detect Ollama models
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.configuration_manager import (
    ConfigurationManager,
    ConfigurationLevel,
    get_configuration_manager
)
from config.ollama_detector import auto_configure_ollama


def view_configuration(args):
    """View current configuration."""
    config_mgr = get_configuration_manager()
    config = config_mgr.load_configuration()
    
    if args.section:
        # Show specific section
        if args.section in config:
            print(json.dumps(config[args.section], indent=2))
        else:
            print(f"Section '{args.section}' not found")
            return 1
    else:
        # Show full configuration
        print(json.dumps(config, indent=2))
    
    return 0


def set_configuration(args):
    """Set configuration value."""
    config_mgr = get_configuration_manager()
    
    # Parse level
    level = ConfigurationLevel.USER
    if args.level:
        try:
            level = ConfigurationLevel(args.level)
        except ValueError:
            print(f"Invalid level: {args.level}")
            print("Valid levels: system, user, workspace")
            return 1
    
    # Parse value (try JSON, fallback to string)
    try:
        value = json.loads(args.value)
    except:
        value = args.value
    
    # Set value
    success = config_mgr.set_configuration_value(args.key, value, level)
    
    if success:
        print(f"✓ Set {args.key} = {value} at {level.value} level")
        return 0
    else:
        print(f"✗ Failed to set {args.key}")
        return 1


def reset_configuration(args):
    """Reset configuration to defaults."""
    config_mgr = get_configuration_manager()
    
    # Parse level
    level = ConfigurationLevel.USER
    if args.level:
        try:
            level = ConfigurationLevel(args.level)
        except ValueError:
            print(f"Invalid level: {args.level}")
            print("Valid levels: user, workspace")
            return 1
    
    # Confirm reset
    if not args.yes:
        response = input(f"Reset {level.value} configuration? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled")
            return 0
    
    # Reset configuration
    success = config_mgr.reset_configuration(level, create_backup=not args.no_backup)
    
    if success:
        print(f"✓ Reset {level.value} configuration")
        return 0
    else:
        print(f"✗ Failed to reset configuration")
        return 1


def export_configuration(args):
    """Export configuration to file."""
    config_mgr = get_configuration_manager()
    
    output_file = Path(args.file)
    success = config_mgr.export_configuration(
        output_file,
        include_sensitive=args.include_sensitive
    )
    
    if success:
        print(f"✓ Exported configuration to {output_file}")
        return 0
    else:
        print(f"✗ Failed to export configuration")
        return 1


def import_configuration(args):
    """Import configuration from file."""
    config_mgr = get_configuration_manager()
    
    input_file = Path(args.file)
    if not input_file.exists():
        print(f"File not found: {input_file}")
        return 1
    
    # Parse level
    level = ConfigurationLevel.USER
    if args.level:
        try:
            level = ConfigurationLevel(args.level)
        except ValueError:
            print(f"Invalid level: {args.level}")
            print("Valid levels: user, workspace")
            return 1
    
    # Import configuration
    success = config_mgr.import_configuration(
        input_file,
        level,
        validate=not args.no_validate
    )
    
    if success:
        print(f"✓ Imported configuration from {input_file}")
        return 0
    else:
        print(f"✗ Failed to import configuration")
        return 1


def list_backups(args):
    """List available backups."""
    config_mgr = get_configuration_manager()
    
    # Parse level filter
    level = None
    if args.level:
        try:
            level = ConfigurationLevel(args.level)
        except ValueError:
            print(f"Invalid level: {args.level}")
            return 1
    
    backups = config_mgr.list_backups(level)
    
    if not backups:
        print("No backups found")
        return 0
    
    print(f"Found {len(backups)} backup(s):")
    print()
    
    for backup_file, timestamp in backups:
        print(f"  {backup_file.name}")
        print(f"    Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    return 0


def restore_backup(args):
    """Restore configuration from backup."""
    config_mgr = get_configuration_manager()
    
    backup_file = Path(args.backup)
    if not backup_file.exists():
        print(f"Backup not found: {backup_file}")
        return 1
    
    # Parse level
    level = ConfigurationLevel.USER
    if args.level:
        try:
            level = ConfigurationLevel(args.level)
        except ValueError:
            print(f"Invalid level: {args.level}")
            print("Valid levels: user, workspace")
            return 1
    
    # Confirm restore
    if not args.yes:
        response = input(f"Restore {level.value} configuration from {backup_file.name}? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled")
            return 0
    
    # Restore backup
    success = config_mgr.restore_backup(backup_file, level)
    
    if success:
        print(f"✓ Restored configuration from {backup_file}")
        return 0
    else:
        print(f"✗ Failed to restore backup")
        return 1


def auto_detect_ollama(args):
    """Auto-detect Ollama models and generate configuration."""
    print("=" * 80)
    print("OLLAMA MODEL AUTO-DETECTION")
    print("=" * 80)
    print()
    
    success, message = auto_configure_ollama()
    
    if success:
        print("✓ SUCCESS")
        print("=" * 80)
        print(message)
        print("=" * 80)
    else:
        print("✗ FAILED")
        print("=" * 80)
        print(message)
        print("=" * 80)
    
    return 0 if success else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="GURU Configuration Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # View command
    view_parser = subparsers.add_parser('view', help='View current configuration')
    view_parser.add_argument('--section', help='Show specific section only')
    view_parser.set_defaults(func=view_configuration)
    
    # Set command
    set_parser = subparsers.add_parser('set', help='Set configuration value')
    set_parser.add_argument('key', help='Configuration key (dot-separated path)')
    set_parser.add_argument('value', help='Configuration value (JSON or string)')
    set_parser.add_argument('--level', choices=['user', 'workspace'], default='user',
                           help='Configuration level (default: user)')
    set_parser.set_defaults(func=set_configuration)
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset configuration to defaults')
    reset_parser.add_argument('--level', choices=['user', 'workspace'], default='user',
                             help='Configuration level (default: user)')
    reset_parser.add_argument('--yes', '-y', action='store_true',
                             help='Skip confirmation prompt')
    reset_parser.add_argument('--no-backup', action='store_true',
                             help='Do not create backup before resetting')
    reset_parser.set_defaults(func=reset_configuration)
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export configuration to file')
    export_parser.add_argument('file', help='Output file path')
    export_parser.add_argument('--include-sensitive', action='store_true',
                              help='Include sensitive data (encrypted)')
    export_parser.set_defaults(func=export_configuration)
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import configuration from file')
    import_parser.add_argument('file', help='Input file path')
    import_parser.add_argument('--level', choices=['user', 'workspace'], default='user',
                              help='Configuration level (default: user)')
    import_parser.add_argument('--no-validate', action='store_true',
                              help='Skip configuration validation')
    import_parser.set_defaults(func=import_configuration)
    
    # Backups command
    backups_parser = subparsers.add_parser('backups', help='List available backups')
    backups_parser.add_argument('--level', choices=['user', 'workspace'],
                               help='Filter by configuration level')
    backups_parser.set_defaults(func=list_backups)
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore configuration from backup')
    restore_parser.add_argument('backup', help='Backup file path')
    restore_parser.add_argument('--level', choices=['user', 'workspace'], default='user',
                               help='Configuration level (default: user)')
    restore_parser.add_argument('--yes', '-y', action='store_true',
                               help='Skip confirmation prompt')
    restore_parser.set_defaults(func=restore_backup)
    
    # Ollama command
    ollama_parser = subparsers.add_parser('ollama', help='Auto-detect Ollama models')
    ollama_parser.set_defaults(func=auto_detect_ollama)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
