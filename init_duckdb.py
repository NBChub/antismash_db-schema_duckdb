import argparse
import csv
import logging
import re
from pathlib import Path

import duckdb
import sqlparse


def convert_serial_to_sequence(sql, schema="antismash"):
    """
    Convert SERIAL columns to SEQUENCE in SQL statements.

    This function processes a given SQL string, identifying CREATE TABLE statements
    and converting any SERIAL column definitions within those statements to use
    SEQUENCEs instead. This is particularly useful for adapting SQL scripts for
    databases that do not support the SERIAL keyword.

    Args:
        sql (str): The SQL script containing one or more SQL statements.

    Returns:
        str: The modified SQL script with SERIAL columns converted to SEQUENCEs.

    The function identifies each CREATE TABLE statement, extracts the table name,
    and searches for SERIAL column definitions. For each SERIAL column found,
    it generates a SEQUENCE and modifies the column definition to use the SEQUENCE
    for its default value. The modified CREATE TABLE statement, along with any
    newly created SEQUENCE declarations, is then included in the returned SQL script.
    """

    # Function implementation remains unchanged
    def replace_serial(table_name, column_name):
        sequence_name = f"{table_name}_{column_name}_seq"
        logging.debug(f"Replacing serial: {sequence_name}")
        sequence_declaration = f"CREATE SEQUENCE {schema}.{sequence_name} START 1;"
        column_declaration = (
            f"{column_name} INTEGER DEFAULT nextval('{schema}.{sequence_name}')"
        )
        return sequence_declaration, column_declaration

    # Split SQL into individual statements
    statements = [
        str(statement).strip()
        for statement in sqlparse.parse(sql)
        if str(statement).strip()
    ]
    processed_statements = []

    for statement in statements:
        # Check if the statement is a CREATE TABLE statement
        if "CREATE TABLE" in statement:
            # Extract the table name
            table_name_match = re.search(r"CREATE TABLE (\w+\.\w+)", statement)
            if table_name_match:
                table_name = table_name_match.group(1).replace(".", "_")

                # Find all serial columns
                pattern = r"(\w+)\s+serial"
                matches = re.findall(pattern, statement)

                sequence_declarations = []
                for column_name in matches:
                    sequence_declaration, column_declaration = replace_serial(
                        table_name, column_name
                    )
                    sequence_declarations.append(sequence_declaration)
                    statement = re.sub(
                        rf"{column_name}\s+serial",
                        column_declaration,
                        statement,
                        count=1,
                    )

                # Add sequence declarations before the CREATE TABLE statement
                processed_statement = (
                    "\n".join(sequence_declarations) + "\n" + statement
                    if sequence_declarations
                    else statement
                )
                processed_statements.append(processed_statement)
            else:
                # If no table name is found, append the original statement
                processed_statements.append(statement)
        else:
            # For non-CREATE TABLE statements, append them as they are
            processed_statements.append(statement)

    # Reassemble the processed statements back into a single SQL string
    modified_sql = ";".join(processed_statements)
    return modified_sql


def convert_postgres_to_duckdb(sql):
    """
    Converts PostgreSQL SQL commands to be compatible with DuckDB.

    Args:
    - sql (str): The PostgreSQL SQL command.

    Returns:
    - str: The converted SQL command for DuckDB.
    """
    # Define conversions for PostgreSQL to DuckDB syntax
    conversions = {
        "TEXT[]": "TEXT",  # DuckDB doesn't support array types directly
        "MATERIALIZED": "",  # DuckDB doesn't support materialized views
        "CURRENT_TIMESTAMP": "CURRENT_TIMESTAMP",  # remains the same
        # Add more conversions as needed
    }

    # Remove lines starting with ---
    sql = re.sub(r"(?m)^\s*---.*\n?", "", sql)

    # Combine multiple spaces into one, replace tabs with a single space, and ensure semicolons are followed by a newline
    sql = re.sub(
        r"\s+", " ", sql
    )  # Replace any whitespace character (space, tab, newline) with a single space
    sql = re.sub(
        r";\s*", ";\n", sql
    )  # Ensure semicolons are followed by exactly one newline

    # Convert CREATE TABLE statements with serial types to use sequences
    sql = convert_serial_to_sequence(sql)

    # Remove or modify unsupported FOREIGN KEY actions
    sql = re.sub(r"ON DELETE SET NULL", "", sql)
    sql = re.sub(r"ON DELETE CASCADE", "", sql)
    sql = re.sub(r"ON DELETE SET DEFAULT", "", sql)

    # Custom modifications for specific tables: as_domains.sql
    sql = re.sub(
        r"follows int4 REFERENCES antismash.as_domains", "follows int4", sql
    )  # remove self reference
    sql = re.sub(
        r"as_domain_id int4 NOT NULL REFERENCES antismash.as_domains",
        "as_domain_id int4 NOT NULL",
        sql,
    )  # remove many to many reference

    for pg_syntax, duckdb_syntax in conversions.items():
        sql = sql.replace(pg_syntax, duckdb_syntax)

    return sql


def sql_to_csv(
    input_sql_file,
    output_csv_file,
    headers=[
        "tax_id",
        "ncbi_taxid",
        "superkingdom",
        "kingdom",
        "phylum",
        "class",
        "taxonomic_order",
        "family",
        "genus",
        "species",
        "strain",
        "name",
    ],
):
    """
    Convert SQL file data to a CSV file.

    This function reads an SQL file, specifically looking for a section of data
    that was exported using the COPY command (common in PostgreSQL dumps), and
    converts this data into a CSV format. The function allows for specifying
    custom headers for the CSV file, which are written as the first row of the
    output CSV file.

    Args:
        input_sql_file (str): Path to the input SQL file containing the data to be converted.
        output_csv_file (str): Path where the output CSV file will be saved.
        headers (list of str): A list of strings representing the column headers for the CSV file.
            Defaults to a predefined list of headers related to taxonomic information.

    The function first identifies the start and end of the data section within the SQL file,
    which is delimited by the COPY command and a terminating "\\.". It then reads the data
    lines, processes them to replace any null values represented by '\\N' with an empty string,
    and writes the processed data to the specified CSV file, including the provided headers.
    """
    logging.info(f"Converting SQL file {input_sql_file} to CSV file...")
    # Open the SQL file and read its contents
    with open(input_sql_file, "r") as sql_file:
        lines = sql_file.readlines()

    # Find the start and end of the data section
    start_index = 0
    end_index = 0
    for i, line in enumerate(lines):
        if line.startswith("COPY"):
            start_index = i + 1
        elif line.strip() == "\\.":
            end_index = i
            break

    # Extract the data lines
    data_lines = lines[start_index:end_index]

    # Open the CSV file for writing
    with open(output_csv_file, "w", newline="") as csv_file:
        writer = csv.writer(
            csv_file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )

        # Write the header row
        writer.writerow(headers)

        # Write the data rows
        for line in data_lines:
            # Split the line into columns based on tab delimiter
            columns = line.strip().split("\t")
            # Replace '\N' with an empty string to handle null values
            columns = [col if col != "\\N" else "" for col in columns]
            writer.writerow(columns)

    logging.info(f"Data successfully written to {output_csv_file}")


def init_duckdb_schema(input_sql_dir, output_dir, duckdb_file=None):
    """
    Initialize a DuckDB schema from SQL files.

    This function creates a DuckDB database schema based on SQL files located in a specified directory.
    It processes each SQL file, converting PostgreSQL-specific syntax to DuckDB-compatible commands where necessary.
    The function also handles special cases for views and tables that require data preloading from CSV files,
    which are generated from specified SQL files.

    Args:
        input_sql_dir (str or Path): The directory containing SQL files for schema creation and data preloading.
        output_dir (str or Path): The directory where the DuckDB database file and any intermediate CSV files will be stored.

    The process involves:
    - Deleting any existing DuckDB database file in the output directory.
    - Creating a new DuckDB database file and connecting to it.
    - Creating a specified schema within the DuckDB database.
    - Processing each SQL file to convert PostgreSQL syntax to DuckDB-compatible syntax.
    - Handling special cases for views and tables that require data preloading, including converting specific SQL files to CSV format and importing them into DuckDB.
    - Writing modified SQL commands to new SQL files in the output directory for record-keeping.

    Special handling is provided for views and tables that require data preloading, with specific SQL commands replaced or augmented by commands to load data from CSV files. This includes creating views for sequence GC content and preloading taxonomic and monomer data from CSV files.
    """

    schema_name = "antismash"
    input_sql_dir = Path(input_sql_dir)
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    # Define the DuckDB database file path
    if duckdb_file is None:
        DUCKDB_FILE = Path(outdir / "antismash_db.duckdb")
        if DUCKDB_FILE.exists():
            DUCKDB_FILE.unlink()
            logging.info(f"Existing file {DUCKDB_FILE} deleted.")
    else:
        DUCKDB_FILE = Path(duckdb_file).resolve()
        assert DUCKDB_FILE.is_file(), f"File not found: {DUCKDB_FILE}"

    logging.info(f"Using DuckDB file: {DUCKDB_FILE}")

    # Connect to DuckDB
    conn = duckdb.connect(str(DUCKDB_FILE))
    logging.info(f"Checking for schema: {schema_name}")

    # Check if the schema exists and create it if it does not
    conn.execute(
        f"CREATE SCHEMA IF NOT EXISTS {schema_name};\nSET SCHEMA '{schema_name}';\n"
    )

    # List of tables and views to process
    TABLES = [
        "sampling_sites",
        "bgc_types",
        "substrates",
        "taxa",
        "profiles",
        "as_domain_profiles",
        "pfams",
        "gene_ontologies",
        "resfams",
        "tigrfams",
        "bgc_rules",
        "samples",
        "isolates",
        "genomes",
        "dna_sequences",
        "regions",
        "candidates",
        "protoclusters",
        "functional_classes",
        "smcogs",
        "cdss",
        "genes",
        "ripps",
        "t2pks",
        "monomers",
        "modules",
        "as_domains",
        "clusterblast_algorithms",
        "clusterblast_hits",
        "tta_codons",
        "pfam_domains",
        "pfam_go_entries",
        "filenames",
        "resfam_domains",
        "tfbs",
        "comparippson",
        "tigrfam_domains",
        "cluster_compare_hits",
        "rel_candidates_protoclusters",
        "rel_candidates_types",
        "rel_candidates_modules",
        "rel_cds_candidates",
        "rel_cds_protoclusters",
        "rel_regions_types",
        "rel_as_domains_substrates",
        "smcog_hits",
        "profile_hits",
        "rel_modules_monomers",
        "view_sequence_gc_content",
        "view_sequence_lengths",
        "preload_taxa",
        "preload_monomers",
    ]

    view_sequence_gc_content = """
    CREATE VIEW antismash.sequence_gc_content AS
    SELECT
        accession,
        ROUND(100.0 * (
            length(dna) - length(replace(dna, 'G', '')) +
            length(dna) - length(replace(dna, 'C', ''))
        ) / length(dna), 2) AS gc_content
    FROM
        antismash.dna_sequences;
    """

    # Convert sql inputs to csv for monomers
    monomer_csv = outdir / "preload_monomers.csv"
    sql_to_csv(
        input_sql_dir / "preload_monomers.sql",
        monomer_csv,
        headers=["monomer_id", "substrate_id", "name", "description"],
    )

    # start seq index at the length of the feeded csv
    last_monomer_id = 1
    with open(monomer_csv, "r") as file:
        for row in csv.reader(file):
            if row:  # Check if the row is not empty
                last_monomer_id = row[0]  # Assuming monomer_id is in the first column
    # The next ID to start from would be the last ID in the CSV +
    next_id_start = int(last_monomer_id) + 1
    logging.info(f"Starting monomer_id sequence at {next_id_start}")
    monomers = f"""
    CREATE SEQUENCE antismash.antismash_monomers_monomer_id_seq START {next_id_start};
    CREATE TABLE antismash.monomers ( monomer_id INTEGER DEFAULT nextval('antismash.antismash_monomers_monomer_id_seq') NOT NULL PRIMARY KEY, substrate_id int4 NOT NULL REFERENCES antismash.substrates, name text NOT NULL, description text, CONSTRAINT monomer_name_unique UNIQUE (name) );
    """

    # Convert sql inputs to csv for taxa
    taxa_csv = outdir / "preload_taxa.csv"
    sql_to_csv(
        input_sql_dir / "preload_taxa.sql",
        taxa_csv,
        headers=[
            "tax_id",
            "ncbi_taxid",
            "superkingdom",
            "kingdom",
            "phylum",
            "class",
            "taxonomic_order",
            "family",
            "genus",
            "species",
            "strain",
            "name",
        ],
    )
    last_taxa_id = 1
    with open(taxa_csv, "r") as file:
        for row in csv.reader(file):
            if row:  # Check if the row is not empty
                last_taxa_id = row[0]  # Assuming monomer_id is in the first column
    # The next ID to start from would be the last ID in the CSV +
    next_id_start = int(last_taxa_id) + 1
    logging.info(f"Starting taxa_id sequence at {next_id_start}")
    taxa = f"""
    CREATE SEQUENCE antismash.antismash_taxa_tax_id_seq START {next_id_start};
    CREATE TABLE antismash.taxa ( tax_id INTEGER DEFAULT nextval('antismash.antismash_taxa_tax_id_seq') NOT NULL, ncbi_taxid int4, superkingdom text, kingdom text, phylum text, CLASS text, taxonomic_order text, family text, genus text, species text, strain text, name text NOT NULL, CONSTRAINT taxa_pkey PRIMARY KEY (tax_id), CONSTRAINT taxa_name_unique UNIQUE (name) );    """

    # Define exceptions for specific tables or views
    duckdb_exceptions = {
        "view_sequence_gc_content": view_sequence_gc_content,
        "preload_taxa": f"COPY antismash.taxa FROM '{taxa_csv}' (AUTO_DETECT TRUE);",
        "preload_monomers": f"COPY antismash.monomers FROM '{monomer_csv}' (AUTO_DETECT TRUE);",
        "monomers": monomers,
        "taxa": taxa,
    }

    # Process each table/view
    for t in TABLES:
        sql_file_path = input_sql_dir / f"{t}.sql"
        if sql_file_path.is_file():
            if t in list(duckdb_exceptions.keys()):
                logging.info(f"Using customized sql for: {t}")
                sql_command = duckdb_exceptions[t]
            else:
                logging.info(f"Creating table: {t}")
                with sql_file_path.open("r") as sql_file:
                    sql_command = sql_file.read()

            sql_command = sqlparse.format(
                sql_command, reindent=False, keyword_case="upper"
            )
            sanitized_sql = convert_postgres_to_duckdb(sql_command)
            # Split the sanitized SQL into individual statements
            statements = [
                str(statement).strip()
                for statement in sqlparse.parse(sanitized_sql)
                if str(statement).strip()
            ]
            statements = [statement for statement in statements if statement != ";"]

            outdir = Path(output_dir)
            outdir.mkdir(parents=True, exist_ok=True)

            with open(outdir / f"{t}.sql", "w") as f:
                statement_tidy = sqlparse.format(
                    "\n".join(statements), reindent=False, keyword_case="upper"
                )
                f.write(statement_tidy)

            for num, statement in enumerate(statements):
                # Ensure the statement is not just whitespace
                if statement.strip():
                    logging.debug(f"Executing DuckDB SQL statement {t}:{num}")
                    try:
                        conn.execute(statement)
                    except Exception as e:
                        logging.error(
                            f"Failed to execute DuckDB SQL statement:\n{statement}\nError: {e}"
                        )
                        try:
                            for n, s in enumerate(statement.split(";")):
                                logging.debug(
                                    f"Executing SQL statement {num}.{n}:\n{s}\n"
                                )
                                conn.execute(s)
                        except Exception as e:
                            logging.error(
                                f"Failed to execute DuckDB SQL statement:\n{statement}\nError: {e}"
                            )
                            exit(1)

        else:
            logging.error(f"No such file: {sql_file_path}")
            exit(1)

    # Close the connection
    conn.close()


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Initialize DuckDB schema from SQL files."
    )
    parser.add_argument("input_sql_dir", help="Directory containing input SQL files")
    parser.add_argument(
        "output_dir",
        help="Directory to store output SQL files and DuckDB database file",
    )
    parser.add_argument(
        "--duckdb-database",
        help="Optional location of the DuckDB database file",
        default=None,
    )
    parser.add_argument(
        "--verbose", help="Increase output verbosity", action="store_true"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    init_duckdb_schema(args.input_sql_dir, args.output_dir, args.duckdb_database)


if __name__ == "__main__":
    main()
