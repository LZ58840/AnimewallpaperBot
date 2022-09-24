#!/bin/bash

set -e
set -a

# https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# https://gist.github.com/mihow/9c7f559807069a03e302605691f85572?permalink_comment_id=3898844#gistcomment-3898844
# shellcheck source=../configs.env
source <(sed -e '/^#/d;/^\s*$/d' -e "s/'/'\\\''/g" -e "s/=\(.*\)/='\1'/g" < "$SCRIPT_DIR/../configs.env")

set +a

docker-compose -f "$SCRIPT_DIR/../docker-compose.yml" up --build --detach --remove-orphans

echo "Waiting for MySQL to start up..."
iter=0
# shellcheck disable=SC2154
while [ $iter -lt 30 ] && ! MYSQL_PWD=$MYSQL_ROOT_PASS mysqladmin ping -h"$MYSQL_HOST" --port "$MYSQL_PORT" -u "root" --silent; do
    sleep 1
    iter=$((iter + 1))
done
