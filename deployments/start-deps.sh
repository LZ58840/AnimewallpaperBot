#!/bin/bash

set -e
set -a

# https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

source "$SCRIPT_DIR/../.env"

set +a

docker-compose -f "$SCRIPT_DIR/docker-compose-test.yml" up --build --detach --remove-orphans

echo "Waiting for MySQL to start up..."
iter=0
# shellcheck disable=SC2154
while [ $iter -lt 60 ] && ! MYSQL_PWD=$MYSQL_ROOT_PASS mysqladmin ping -h"127.0.0.1" --port "3306" -u "root" --silent; do
    sleep 1
    iter=$((iter + 1))
done
