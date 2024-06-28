# DuckDB Schema Initialization for antiSMASH Database

This guide provides instructions on how to Initialize a local [antiSMASH Database schema](https://github.com/antismash/db-schema.git) using DuckDB.

## Quick Start
1. Setup the database and importer requirements following this step:

    ```bash
    # Part 1: Build database from schema
    git clone git@github.com:NBChub/antismash_db-schema_duckdb.git
    cd antismash_db-schema_duckdb
    python -m venv antismash_db_duckb
    source ./antismash_db_duckb/bin/activate
    pip install -r requirements.txt
    git clone https://github.com/antismash/db-schema.git
    python init_duckdb.py db-schema duckdb-schema
    deactivate

    # Part 2: Setup importer requirements
    mamba env create -f env.yaml
    conda run -n antismash_db_env bash env.post-deploy.sh
    conda activate antismash_db_env
    # 1. Download NCBI taxdump:
    wget -P ncbi-taxdump https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz -nc
    (cd ncbi-taxdump && tar -xvf new_taxdump.tar.gz)
    # 2. Install NCBI taxonomy handler to create the JSON taxdump (requires Rust):
    cargo install asdb-taxa
    # don't forget to export the .cargo/bin to path
    export PATH="$HOME/.cargo/bin:$PATH"
    # 3. Clone the JSON importer:
    git clone git@github.com:matinnuhamunada/db-import.git
    (cd db-import && git checkout v4.0.0-duckdb)
    ```

2. Setting Up Environment Variables. Get your Entrez API Key [here](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/).

    ```bash
    export ASDBI_ENTREZ_API_KEY=<your_entrez_api_key>
    ```

3. Populate database with antiSMASH results

    ```bash
    bash full_workflow.sh <your antiSMASH output directory>
    ```

## Usage
### Step 1: Building the Database from Schema

1. Clone this repository

   First, clone this repository to your local machine using the following Git command:

   ```bash
   git clone git@github.com:NBChub/antismash_db-schema_duckdb.git
   cd antismash_db-schema_duckdb
   ```

2. Create a Virtual Environment & Install Dependencies

    Create a virtual environment using `venv`. This helps to isolate your project's dependencies from your system-wide Python packages.

    Open your terminal and navigate to your project directory, then run:

    ```bash
    python -m venv antismash_db_duckb
    source ./antismash_db_duckb/bin/activate
    pip install -r requirements.txt
    deactivate
    ```

3. Initialize the DuckDB Schema

    Use the `init_duckdb.py` script to initialize the DuckDB schema. You need to specify the directory of the cloned SQL files and the output directory for the DuckDB schema files.

    - `db-schema`: The directory containing the SQL files cloned from the [antiSMASH DB schema](https://github.com/antismash/db-schema.git) repository.
    - `duckdb-schema`: The directory where the DuckDB schema files will be stored.

    ```bash
    source ./antismash_db_duckb/bin/activate
    git clone https://github.com/antismash/db-schema.git
    python init_duckdb.py db-schema duckdb-schema
    deactivate
    ```
### Step 2: Installing prerequisites for importing JSONs

Before you start, make sure you have the following:

- Conda/Mamba: You can install it by following the instructions [here](https://github.com/conda-forge/miniforge#mambaforge).

Then follow these steps to install the required packages and repositories:
1. Create the Conda environment by:

    ```bash
    mamba env create -f env.yaml
    conda run -n antismash_db_env bash env.post-deploy.sh
    ```

2. Install the necessary components for the importer:

    ```bash
    # Activate the Conda environment:
    conda activate antismash_db_env

    # 1. Download NCBI taxdump:
    wget -P ncbi-taxdump https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz -nc
    (cd ncbi-taxdump && tar -xvf new_taxdump.tar.gz)

    # 2. Install NCBI taxonomy handler to create the JSON taxdump (requires Rust):
    cargo install asdb-taxa
    # don't forget to export the .cargo/bin to path
    export PATH="$HOME/.cargo/bin:$PATH"

    # 3. Clone the JSON importer:
    git clone git@github.com:matinnuhamunada/db-import.git
    (cd db-import && git checkout v4.0.0-duckdb)
    ```

## Importing antiSMASH JSONs to the database
The script will process the antiSMASH schema SQL files in the specified input directory (`db-schema`), convert them to be compatible with DuckDB, and then initialize the schema in the specified output directory (`duckdb-schema`). In the output folder, you can find the DuckDB database file (`duckdb-schema/antismash_db.duckdb`) and the converted SQL schema files.


### Setting Up Environment Variables
Before you start, you need to generate an Entrez API Key. The Entrez API Key is used to access NCBI's suite of interconnected databases (including PubMed, GenBank, and more) through their E-utilities API. You can find instructions on how to generate your Entrez API Key [here](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/).

Once you have your Entrez API Key, you need to set up the following environment variables:

- `ASDBI_ENTREZ_API_KEY`: This should be your Entrez API key.

You can set these variables in your environment by adding them to a `.env` file in the root directory of your project. The `.env` file should look like this:

```bash
export ASDBI_ENTREZ_API_KEY=<your_entrez_api_key>
echo "export ASDBI_ENTREZ_API_KEY=$ASDBI_ENTREZ_API_KEY" > .env
```

Replace `your_entrez_api_key` with your actual Entrez API key.

After you've added these variables to your .env file, you can load them into your environment by running:

```bash
source .env
```

This command reads the `.env` file and exports the variables so they can be accessed by scripts and applications running in your shell.

### Importing JSON to the database
You can run the `full_workflow.sh` to import your antiSMASH results to the database:

```bash
bash full_workflow.sh <your antiSMASH output directory>
```

For example, you can fetch the _S. coelicolor_ example and add it to the database:

```bash
 wget https://antismash-db.secondarymetabolites.org/output/GCF_008931305.1/GCF_008931305.1.json -nc -P input_files/
 bash full_workflow.sh input_files/
```

## Exploring and visualizing the database
There are multiple ways to interact with the DuckDB database. We recommend to start with [DBeaver](https://dbeaver.com/) for an easy start.
Otherwise, refer to the [DuckDB documentation](https://duckdb.org/docs/index).
