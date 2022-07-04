#!/bin/bash

username=${1:-root}
echo "Connecting to MySQL as $username..."
echo "You will be prompted to enter the root password."

bot_pass=$(date +%s | sha256sum | base64 | head -c 32 ; echo)

mysql -u "$username" -p <<SETUP
SET @usr = "animewallpaperbot";
SET @pwd = "$bot_pass";
\. setup/user.sql
\. setup/database.sql
\. setup/tables.sql
\. setup/events.sql
\. setup/functions.sql
SETUP

json_conf='{"user": "animewallpaperbot", "password":"'"$bot_pass"'", "database": "animewallpaper"}'

echo "$json_conf" > config/config_db.json
echo "The generated credentials for the bot is stored in ./config/config_db.json"
echo "Setup successful."
