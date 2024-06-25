# DuckDB Schema Initialization for antiSMASH Database

This guide provides instructions on how to initialize a DuckDB schema using SQL files from the antiSMASH database schema repository.

## Quick Start

```bash
set -e
git clone git@github.com:matinnuhamunada/antismash_db_duckdb.git
cd antismash_db_duckdb
python -m venv antismash_db_duckb
source ./antismash_db_duckb/bin/activate
pip install -r requirements.txt
bash init.sh
deactivate
```

## Getting Started

1. Clone this repository

   First, clone this repository to your local machine using the following Git command:

   ```bash
   git clone git@github.com:matinnuhamunada/antismash_db_duckdb.git
   ```

2. Create a Virtual Environment & Install Dependencies

    Create a virtual environment using `venv`. This helps to isolate your project's dependencies from your system-wide Python packages.

    Open your terminal and navigate to your project directory, then run:

    ```bash
    python -m venv antismash_db_duckb
    source antismash_db_duckdb/bin/activate
    pip install -r requirements.txt
    ```

3. Initialize the DuckDB Schema

    Use the `init_duckdb.py` script to initialize the DuckDB schema. You need to specify the directory of the cloned SQL files and the output directory for the DuckDB schema files.

    - `db-schema`: The directory containing the SQL files cloned from the [antiSMASH DB schema](https://github.com/antismash/db-schema.git) repository.
    - `duckdb-schema`: The directory where the DuckDB schema files will be stored.

    Example:

    ```bash
    git clone https://github.com/antismash/db-schema.git
    python init_duckdb.py db-schema duckdb-schema
    ```

## What Happens Next?
The script will process the SQL files in the specified input directory (db-schema), convert them to be compatible with DuckDB, and then initialize the schema in the specified output directory (duckdb-schema). This includes creating a DuckDB database file and converting and storing the SQL schema files.
