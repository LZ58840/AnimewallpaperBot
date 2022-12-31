# AnimewallpaperBot v2.0 beta
A specialized moderation bot for /r/Animewallpaper and possibly some other wallpaper subs.

## Features
- Per-flair moderator settings
- ~~Resolution Tag Detection (ResolutionAny)~~
- Mismatched Resolution Detection (ResolutionMismatch)
- Resolution Thresholds (ResolutionBad)
- Aspect Ratio Thresholds (AspectRatioBad)
- [Planned] Source Comment Detection (SourceAny)
- [Planned] Rate Limiting (RateLimit)
- [Planned] Repost Detection (RepostAny)
- [Planned] Interactive features i.e. manual triggering

## Observed Bugs
- [Completed] Async threads crash from PRAW requests
- [In progress] Error handling, better logging

## Quick Start Guide
Complete and rename the file `.env-example` to `.env`. You will need a Reddit account with its client ID and client secret available, visit [this page](https://www.reddit.com/prefs/apps/) to register. To get a refresh token, visit [this page](https://asyncpraw.readthedocs.io/en/stable/tutorials/refresh_token.html#refresh-token) and follow the instructions. To access the Imgur API, you will also need a client ID, visit [this page](https://apidocs.imgur.com/) to register. To run the tests, you will need a second account (with client ID and secret) to act as a regular user.

Additionally, please visit [this page](https://github.com/noxdafox/rabbitmq-message-deduplication) and download the latest version of the RabbitMQ Message Deduplication Plugin. Put the two `*.ez` files into `deployments/rabbit/plugins`.

Ensure your machine has Makefile and Docker installed and running. Run `make setup` to arrange and start the Docker Compose network.

For now, you must add your subreddits manually (double check that your moderator account has Flair, Modmail, Posts/Comments, and Wiki permissions). Connect to the MySQL container and run:
```mysql
INSERT INTO awb.subreddits(name, latest_utc) VALUES ('<your subreddit name>', UNIX_TIMESTAMP());
```

Once added, the program will auto-generate in your subreddit wiki a default configuration in the page named `awb` if it does not already exist. Moderation settings are disabled by default until you enable them accordingly, but the program will start collecting submission and image data immediately.

## Settings
TBA

## Makefile
TBA

## Testing
TBA