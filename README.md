# Telegram Short Finance Bot
Telegram botfor short finance

## About
**(TGmainbot) is a bot library that allows you to get notification about events on https://app.shorter.finance/dashboard

This is a functioning proof-of-concept project with known bugs. Feel free to fork, share and drop me a line.

## Features
* Price alerts notifications for any cryptocurrency present on CoinGecko api
* New pool,proposals,auction notifications on Shorter Finance
* Pools expiration notifications on Shorter Finance (presets: 3 days, 1 day, 12 hours, 6 hours, 3 hours, 1 hours, 15 minutes)
* Run bot in the cloud while you sleep. Support for Docker Compose

## Requirements
### OS / Infrastructure
* Python 3+
* Docker (optional)
* Telegram (Desktop, Web or Mobile download: https://www.telegram.org/)
* MongoDB

## Quick Start

### Setup your ENV vars
Edit the file src/.env which contains all the required environmental variables for bot

### Running Docker Compose

* running 'docker-compose up -d' to build the Docker containers which include the Mongo database r:

* 'docker-compose down' to stop the containers

Before you were required to run your own Mongo instance and this created some issues with connection string compatability and versioning. In this update, it is just created for you and persisted on disk.

Additionally Dozzle is provided so that you may view logs in your browser, simply go to http://localhost:9999 and click on the `app_bot` container.


### Telethon SDK
The bot is built on top of the Telethon Python SDK (https://docs.telethon.dev/en/latest/)

A few things to note and gotchas encountered in building this proof of concept:

1. **Rate Limiting**
Telegram does intense rate limiting which will throw FloodWaitErrors. 
In my research it seems like no one knows the algorithm for this but 
you want your back off waits to scale in response because when you 
violate and exceed the unknown rate limit, the waits become 
exponential. I’ve found a happy medium with my approach to waiting.

FloodWaitErrors can occur when you are submitting too many requests 
to the API whether it is querying users information or joining  too many 
channels too fast

2. **Telethon Sessions**
Telethon will create a session file. You can set the name of the session 
file when you instantiate the Telethon client: 

`TelegramClient(<session_file_name>, <api_user_id>, <api_user_hash>)`

	This file happens to be a sqlite database which you can connect to. It 	
	acts like a cache and stores historical data as well as your session 
	authentication information so you will not have to re-authenticate with 
	Telegram’s 2FA . Note that you will need to login for a first time and 
	authenticate when you first use the API.
