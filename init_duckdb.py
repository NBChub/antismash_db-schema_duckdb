import argparse
import csv
import logging
import re
from pathlib import Path

import duckdb
import sqlparse


def convert_serial_to_sequence(sql):
    def replace_serial(table_name, column_name):
        sequence_name = f"{table_name}_{column_name}_seq"
        logging.debug(f"Replacing serial: {sequence_name}")
        sequence_declaration = f"CREATE SEQUENCE {sequence_name} START 1;"
        column_declaration = f"{column_name} INTEGER DEFAULT nextval('{sequence_name}')"
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

    # Remove lines from 'COMMENT' to ';'
    sql = re.sub(r"COMMENT.*?;", "", sql, flags=re.DOTALL)

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


def init_duckdb_schema(input_sql_dir, output_dir):
    schema_name = "antismash"
    input_sql_dir = Path(input_sql_dir)
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    # Define the DuckDB database file path
    DUCKDB_FILE = Path(outdir / "antismash_db.duckdb")
    if DUCKDB_FILE.exists():
        DUCKDB_FILE.unlink()
        logging.info(f"Existing file {DUCKDB_FILE} deleted.")

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

    taxa_csv = outdir / "preload_taxa.csv"
    monomer_csv = outdir / "preload_monomers.csv"

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
    sql_to_csv(
        input_sql_dir / "preload_monomers.sql",
        monomer_csv,
        headers=["monomer_id", "substrate_id", "name", "description"],
    )

    # Define exceptions for specific tables or views
    duckdb_exceptions = {
        "view_sequence_gc_content": view_sequence_gc_content,
        "preload_taxa": f"COPY antismash.taxa FROM '{taxa_csv}' (AUTO_DETECT TRUE);",
        "preload_monomers": f"COPY antismash.monomers FROM '{monomer_csv}' (AUTO_DETECT TRUE);",
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
        "--verbose", help="Increase output verbosity", action="store_true"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    init_duckdb_schema(args.input_sql_dir, args.output_dir)


if __name__ == "__main__":
    main()
