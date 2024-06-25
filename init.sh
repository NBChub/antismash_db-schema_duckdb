set -e

git clone https://github.com/antismash/db-schema.git
python init_duckdb.py db-schema duckdb-schema
