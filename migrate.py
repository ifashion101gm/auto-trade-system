#!/usr/bin/env python3
"""Database Migration Management Script for VMassit.

Provides easy-to-use commands for managing database migrations:
- migrate upgrade    - Apply all pending migrations
- migrate downgrade  - Rollback last migration
- migrate status     - Show current migration status
- migrate history    - Show migration history
- migrate current    - Show current migration version
"""

import os
import sys
from pathlib import Path
import subprocess

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))


def run_alembic_command(command: str, *args) -> int:
    """Run an alembic command and return exit code."""
    alembic_ini = project_root / "alembic.ini"
    
    cmd = [
        sys.executable, "-m", "alembic",
        "-c", str(alembic_ini),
        command
    ] + list(args)
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def main():
    """Main entry point for migration management."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("Available commands:")
        print("  upgrade    - Apply all pending migrations")
        print("  downgrade  - Rollback last migration")
        print("  status     - Show current migration status")
        print("  history    - Show migration history")
        print("  current    - Show current migration version")
        print("  revision   - Create new migration (usage: migrate revision 'description')")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "upgrade":
        exit_code = run_alembic_command("upgrade", "head")
        
    elif command == "downgrade":
        # Default to one step back, or accept specific version
        version = sys.argv[2] if len(sys.argv) > 2 else "-1"
        exit_code = run_alembic_command(f"downgrade {version}")
        
    elif command == "status":
        exit_code = run_alembic_command("current")
        if exit_code == 0:
            print("\nMigration Status:")
            run_alembic_command("heads")
            
    elif command == "history":
        exit_code = run_alembic_command("history")
        
    elif command == "current":
        exit_code = run_alembic_command("current")
        
    elif command == "revision":
        description = sys.argv[2] if len(sys.argv) > 2 else "auto_migration"
        exit_code = run_alembic_command(f"revision -m '{description}' --autogenerate")
        
    else:
        print(f"Unknown command: {command}")
        print("Use 'migrate' without arguments to see available commands")
        sys.exit(1)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
