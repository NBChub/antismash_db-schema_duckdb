set -e

if [ ! -d "db-schema" ]; then
  git clone https://github.com/antismash/db-schema.git
else
  echo "The directory 'db-schema' already exists, skipping clone."
fi

python init_duckdb.py db-schema duckdb-schema
