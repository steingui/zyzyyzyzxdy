#!/bin/bash

# Load environment variables
set -a
source .env
set +a

# Run migration
.venv/bin/python scripts/run_migration.py "$@"
