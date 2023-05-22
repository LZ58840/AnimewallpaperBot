![](https://raw.githubusercontent.com/LZ58840/AnimewallpaperBot/main/banner.png)
# AnimewallpaperBot v2.1.1
A specialized moderation bot for /r/Animewallpaper and possibly some other wallpaper subreddits I moderate.

## Features
- Mismatched Resolution Detection (ResolutionMismatch)
- Resolution Thresholds (ResolutionBad)
- Aspect Ratio Thresholds (AspectRatioBad)
- Source Comment Detection (SourceCommentAny)
- Rate Limiting (RateLimitAny)

## Quick Start Guide
Complete and rename the file `.env-example` to `.env`. You will need a Reddit account with its client ID and client secret available, visit [this page](https://www.reddit.com/prefs/apps/) to register. To get a refresh token, visit [this page](https://asyncpraw.readthedocs.io/en/stable/tutorials/refresh_token.html#refresh-token) and follow the instructions. To access the Imgur API, you will also need a client ID, visit [this page](https://apidocs.imgur.com/) to register. To run the tests, you will need a second account (with client ID and secret) to act as a regular user.

Additionally, please visit [this page](https://github.com/noxdafox/rabbitmq-message-deduplication) and download the latest version of the RabbitMQ Message Deduplication Plugin. Put the two `*.ez` files into `deployments/rabbit/plugins`.

Ensure your machine has Makefile and Docker installed and running. Run `make setup` to arrange and start the Docker Compose network.

## Adding AWB as moderator to a subreddit
For now, you must add your subreddits manually (double check that your moderator account has Flair, Modmail, Posts/Comments, and Wiki permissions). Connect to the MySQL container and run:
```mysql
INSERT INTO awb.subreddits(name, latest_utc) VALUES ('<your subreddit name>', UNIX_TIMESTAMP());
```

## Settings
Once added, the program will auto-generate in your subreddit wiki a default configuration in the page named `awb` if it does not already exist. Moderation settings are disabled by default until you enable them accordingly, but the program will start collecting submission and image data immediately. YAML format is used.


## Makefile
- `start` - start the deployment on docker-compose.
- `setup` - create the SQL tables, if they do not exist.
- `stop` - stop the deployment on docker-compose.
- `restart` - stop and start the deployment on docker-compose.
- `clean` - stop deployment and clear any data volumes.
- `reset` - clean and setup deployment.
- `start_dc` - start dependencies only (RabbitMQ and MySQL).
- `stop_dc` - stop dependencies and clear data volumes.

## Testing
Run `make integ` to have unittest run all the integration tests. Testing is mostly outdated and slow. It was intended to test version 1.0.

## Credits
- Profile picture: [source artwork by るびぃ on pixiv](https://www.pixiv.net/en/artworks/33861959)
- Banner: [source image from the Fandom wiki](https://toarumajutsunoindex.fandom.com/wiki/Electron_(NV)_Goggles?file=Goggles.PNG), [source font](https://www.dafont.com/elementalend.font)