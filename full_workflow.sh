#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Default values
SCRIPT_DIR=$(dirname "$0")
SEQDIR=""
VERBOSE=false
ALLOWED_ASSEMBLY_PREFIX="GCA,GCF"
ERROR_FILE=import_errors.txt

# Function to display help message
show_help() {
  cat << EOF
Usage: $(basename "$0") SEQDIR [options]

Positional Arguments:
  SEQDIR                       Set the sequence directory. This option is required.

Options:
  -v, --verbose                Enable verbose logging.
  -p, --allowed_assembly_prefix   Comma-separated list of allowed assembly prefixes. Default is 'GCA,GCF'.
  -h, --help                   Display this help message and exit.
EOF
}

# Parse command-line options and positional arguments
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    -p|--allowed_assembly_prefix)
      ALLOWED_ASSEMBLY_PREFIX="$2"
      shift 2
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      if [ -d "$1" ]; then
        SEQDIR="$1"
        shift
      else
        echo "Unknown option or invalid directory: $1"
        show_help
        exit 1
      fi
      ;;
  esac
done

# Check if SEQDIR is provided
if [ -z "$SEQDIR" ]; then
  echo "Error: Sequence directory (SEQDIR) is required."
  show_help
  exit 1
fi

# Create necessary files
touch imported.txt deferred_imported.txt
rm -f "$ERROR_FILE"

# Copy the database if it does not exist
if [ ! -f antismash_db.duckdb ]; then
  cp "$SCRIPT_DIR/duckdb-schema/antismash_db.duckdb" antismash_db.duckdb
  echo "Database copied."
else
  echo "Database already exists."
fi

# Verbose logging
log() {
  if [ "$VERBOSE" = true ]; then
    echo "$1"
  fi
}

log "Importing taxonomy"
asdb-taxa init --cache "$SCRIPT_DIR/asdb_cache.json" --datadir "$SEQDIR" --mergeddump "$SCRIPT_DIR/ncbi-taxdump/merged.dmp" --taxdump "$SCRIPT_DIR/ncbi-taxdump/rankedlineage.dmp"

log "Importing base results"
find "$SEQDIR" -name "*.json" | while read -r infile; do
  if grep -q "$infile" imported.txt; then
    log "Skipping $infile"
    continue
  fi
  log "Importing $infile"
  if "$SCRIPT_DIR/db-import/import_json.py" --taxonomy "$SCRIPT_DIR/asdb_cache.json" "$infile" --allowed_assembly_prefix "$ALLOWED_ASSEMBLY_PREFIX"; then
    echo "$infile" >> imported.txt
  else
    echo "$infile" >> "$ERROR_FILE"
    false  # marks the loop as a failure, but doesn't _exit_ the loop
  fi
done || { echo "Skipping deferred imports due to at least one base result import failure (see '$ERROR_FILE')"; exit 1; }
