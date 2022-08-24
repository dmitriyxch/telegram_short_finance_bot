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
Edit the file sample.env which contains all the required environmental variables for bot

* Replace W3_NODE_URL,free rpc nodes on https://www.alchemy.com/ or https://infura.io/
* TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN
* Rename sample.env to .env 'mv sample.env .env'

### Running Docker Compose

* running 'sudo docker-compose up -d' to build the Docker containers which include the Mongo database r:

* 'sudo docker-compose down' to stop the containers

Before you were required to run your own Mongo instance and this created some issues with connection string compatability and versioning. In this update, it is just created for you and persisted on disk.

Additionally Dozzle is provided so that you may view logs in your browser, simply go to http://localhost:9999 and click on the `app_bot` container.

### Notes

MongoDB saves data by path ~/docker/mongo

How bot works demo https://youtu.be/h2f-1uD64AE

Demo bot address https://t.me/shfinancebot

How to add bot to the group https://www.youtube.com/watch?v=UIsF8ki4ewM

Manage notifications in chats in Profile menu (Default On)
On - bot sends notifications to the groups
Off -  bot sends notifications to private chat


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
