#!/bin/bash

set -e
set -a

# https://stackoverflow.com/questions/59895/how-to-get-the-source-directory-of-a-bash-script-from-within-the-script-itself
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# https://gist.github.com/mihow/9c7f559807069a03e302605691f85572?permalink_comment_id=3898844#gistcomment-3898844
# shellcheck source=../configs.env
source <(sed -e '/^#/d;/^\s*$/d' -e "s/'/'\\\''/g" -e "s/=\(.*\)/='\1'/g" < "$SCRIPT_DIR/../configs.env")

set +a

echo "Turning off MySQL strict mode..."
MYSQL_PWD=$MYSQL_ROOT_PASS mysql -h "$MYSQL_HOST" --port "$MYSQL_PORT" -u "root" -e "SET GLOBAL sql_mode = 'NO_ENGINE_SUBSTITUTION';"

echo "Creating MySQL tables..."
for sql_file in "$SCRIPT_DIR/sql"/*.sql; do
  echo "-- $sql_file"
  set +e
	MYSQL_PWD=$MYSQL_ROOT_PASS mysql -h "$MYSQL_HOST" --port "$MYSQL_PORT" -u "root" --database animewallpaper < "$sql_file"
  set -e
done
