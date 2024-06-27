#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

touch imported.txt
touch deferred_imported.txt

ERROR_FILE=import_errors.txt

rm -f $ERROR_FILE

IMPORTDIR=`dirname "$0"`
readonly SEQDIR=$1

if [ ! -f antismash_db.duckdb ]; then
    cp $IMPORTDIR/duckdb-schema/antismash_db.duckdb antismash_db.duckdb
    echo "Database copied."
else
    echo "Database already exists."
fi

echo "Importing taxonomy"
asdb-taxa init --cache $IMPORTDIR/asdb_cache.json --datadir $SEQDIR --mergeddump $IMPORTDIR/ncbi-taxdump/merged.dmp --taxdump $IMPORTDIR/ncbi-taxdump/rankedlineage.dmp

echo "Importing base results"
for infile in $(find ${SEQDIR} -name "*.json"); do
    grep -q ${infile} imported.txt && echo "Skipping ${infile}" && continue
    echo "importing ${infile}"
    if $IMPORTDIR/db-import/import_json.py --taxonomy $IMPORTDIR/asdb_cache.json ${infile}; then
        echo ${infile} >> imported.txt
    else
        echo ${infile} >> $ERROR_FILE
        false  # marks the loop as a failure, but doesn't _exit_ the loop
    fi
done || { echo "Skipping deferred imports due to at least one base result import failure (see '$ERROR_FILE')"; exit 1;}
