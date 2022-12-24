#!/bin/bash

set -e
set -a

# https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

source "$SCRIPT_DIR/../.env"

set +a

echo "Turning off MySQL strict mode..."
MYSQL_PWD=$MYSQL_ROOT_PASS mysql -h"127.0.0.1" --port "3306" -u "root" -e "SET GLOBAL sql_mode = 'NO_ENGINE_SUBSTITUTION';"

echo "Creating MySQL tables..."
set +e
MYSQL_PWD=$MYSQL_ROOT_PASS mysql -h"127.0.0.1" --port "3306" -u "root" --database awb < "$SCRIPT_DIR/setup.sql"
set -e
