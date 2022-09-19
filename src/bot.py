import asyncio
from telethon import TelegramClient, events, Button, types 


import pymongo
from pathlib import Path
from loguru import logger
import datetime
from dotenv import load_dotenv
import os
import price

env_file = '../.env' if os.path.isfile('../.env') else 'bot.env'
logger.info(f'env_file: {env_file}')
dotenv_path = Path(env_file)
load_dotenv(dotenv_path=dotenv_path)


class TGmainbot:

    def __init__(self, tg_client: TelegramClient, mongo_client: pymongo.MongoClient, cache_time_price_list, cache_time_price):
        # mongo init
        self.mongo_db = mongo_client
        self.db = self.mongo_db["telegram_db"]
        self.users_collection = self.db["users"]
        self.token_alerts_collection = self.db["token_alerts"]
        self.proposal_collection = self.db["proposal_alerts"]
        self.pool_collection = self.db["pool_alerts"]
        self.profiles = self.db["profiles"]
        self.auction_collection = self.db["auction_alerts"]
        self.expiration_collection = self.db["expiration_alerts"]

        self.cache_time_price_list = cache_time_price_list
        self.cache_time_price = cache_time_price
        self.get_price = price.Price(
            self.mongo_db, cache_time_price_list=self.cache_time_price_list, cache_time_price=self.cache_time_price)

        self.cancel_messages = {}

        # tg events setup
        self.tg_client = tg_client
        self.tg_client.add_event_handler(
            self.chat_handler, events.ChatAction())
        self.tg_client.add_event_handler(
            self.handler, events.NewMessage(pattern='/start'))
        self.tg_client.add_event_handler(self.callback, events.CallbackQuery)
        self.tg_client.add_event_handler(
            self.price_alert, events.NewMessage(pattern='.{2}Price Alerts'))
        self.tg_client.add_event_handler(
            self.proposal_alert, events.NewMessage(pattern='.{2}New Proposal Alerts'))
        self.tg_client.add_event_handler(
            self.pool_alert, events.NewMessage(pattern='.{2}New Pool Alerts'))
        self.tg_client.add_event_handler(
            self.auction_alert, events.NewMessage(pattern='.{2}New Auction Alerts'))
        self.tg_client.add_event_handler(
            self.profile_settings, events.NewMessage(pattern='Profile'))
        self.tg_client.add_event_handler(
            self.pool_exp_alert, events.NewMessage(pattern='.{2}Pool Expiration Alerts'))
        self.tg_client.add_event_handler(
            self.edit_coin, events.NewMessage(pattern='/edit_c.+'))
        self.tg_client.run_until_disconnected()

    # callback for all inline buttons
    async def callback(self, event):
        try: 
            user = await event.get_sender()

            if 'Cancel' in str(event.data):
                # logger.info(event)
                if user.id in self.cancel_messages:
                    logger.debug(
                        f'{user.first_name} canceled the operation message: {self.cancel_messages[user.id]}')
                    async with self.tg_client.conversation(event.chat_id, exclusive=False) as conv:
                        await conv.cancel_all()
                    await self.tg_client.delete_messages(event.chat_id, [self.cancel_messages[user.id]])
                    del self.cancel_messages[user.id]
                    logger.debug(self.cancel_messages)

            elif 'select_' in str(event.data) or 'change_' in str(event.data):
                token_id = str(event.data).split("'")[1].replace('select_', '').replace('change_', '').replace('_', '-')
                coin = self.get_price.get_token(token_id)
                logger.debug(coin)
                async with self.tg_client.conversation(event.chat_id) as conv:
                    if self.token_alerts_collection.count_documents({"user_id": user.id, "token_id": token_id}) == 0 or 'change_' in str(event.data):
                        keyboard = [
                            [
                                Button.inline("❌ Cancel ", f'Cancel'),
                            ]
                        ]
                        cancel_message = await conv.send_message(f'{coin["name"]} ({coin["symbol"].upper()}) - ${coin["current_price"]}\nEnter % price change of {coin["symbol"].upper()} to receive notifications:', buttons=keyboard)
                        self.cancel_messages[user.id] = cancel_message
                        response_coin = await conv.get_response()
                        logger.debug(response_coin)
                        change_percent = round(float(response_coin.message),2)
                        if change_percent:
                            self.token_alerts_collection.delete_one({"user_id": user.id, "token_id": token_id})
                            self.token_alerts_collection.insert_one(
                                {"user_id": user.id, "token_id": token_id, "change_percent": change_percent, "last_price": coin["current_price"], "last_update": datetime.datetime.utcnow().isoformat()})

                            keyboard = [
                                [
                                    Button.inline("🚀 Add more", b'Add coin')
                                ]
                            ]
                            await conv.send_message(f'Coin {coin["symbol"].upper()} was added to Main watchlist!', buttons=keyboard)
                    else:
                        await conv.send_message(f'{coin["symbol"].upper()} token is already in your watchlist.')
                    
                    
                        
            elif 'Edit coins list' in str(event.data):
                async with self.tg_client.conversation(event.chat_id) as conv:
                    message = 'Main profile. Select Coin to edit:\n'
                    for coin in self.token_alerts_collection.find({"user_id":user.id}):
                        coin = self.get_price.get_token(coin["token_id"])
                        message += f'{coin["symbol"].upper()} is ${coin["current_price"]} /edit_c_{coin["id"].replace("-", "_")}\n'
                    await conv.send_message(message)
                    
            elif 'delete_c_' in str(event.data):
                token_id = str(event.data).split("'")[1].replace('delete_c_', '').replace('_', '-')
                coin = self.get_price.get_token(token_id)
                async with self.tg_client.conversation(event.chat_id) as conv:
                    self.token_alerts_collection.delete_one({"user_id": user.id, "token_id": token_id.replace("_", "-")})
                    await conv.send_message(f'{coin["name"]} has been successfully removed from your watchlist')
                    
            elif 'group_set_' in str(event.data):
                group_id = int(str(event.data).split("'")[1].replace('group_set_', '').replace('_', '-'))
                group = self.profiles.find_one({"id":group_id, "user_id":user.id})
                status = False if group["notifications"] == True else True
                on = "Off" if group['notifications'] else "On"
                self.profiles.find_one_and_update({"id":group_id, "user_id":user.id}, {"$set":{"notifications":status}})
                
                async with self.tg_client.conversation(event.chat_id) as conv:
                    await conv.send_message(f'{group["title"]} set status notification to {on}')
                        
            
                    

            elif 'Add coin' in str(event.data):
                keyboard = [
                    [
                        Button.inline("❌ Cancel ", f'Cancel'),
                    ]
                ]
                async with self.tg_client.conversation(event.chat_id) as conv:
                    cancel_message = await conv.send_message('Enter coin symbol or name (e.g BTC, LINK) or token contract address:', buttons=keyboard)
                    self.cancel_messages[user.id] = cancel_message
                    response_coin = await conv.get_response()
                    logger.debug(response_coin)

                    coins = self.get_price.search_by_ticker(response_coin.message)
                    logger.debug(coins)
                    if len(coins) > 0:
                        keyboard_coin = []
                        kb_cnt = 0
                        kb_msg = ''
                        for coin in coins:
                            kb_cnt += 1
                            logger.debug(coin)
                            keyboard_coin.append(Button.inline(
                                str(kb_cnt), f'select_{coin["id"].replace("-", "_")}'))
                            kb_msg += f'{kb_cnt}. {coin["name"]} ({coin["symbol"].upper()}) \n ${coin["current_price"]} \n Market Cap: ${round(float(coin["market_cap"])/10e+5,2)}m\n'

                        await conv.send_message(f'Choose your coin:\n {kb_msg}', buttons=keyboard_coin)

                    else:
                        await conv.send_message(f'Can not find coin {response_coin}')
                        
            elif "set" in str(event.data):
                async with self.tg_client.conversation(event.chat_id) as conv:
                    pool_alert = int(str(event.data).split(" ")[1].replace("'",""))
                    #pool_id = int(str(event.data).split(" ")[2].split("'")[0])  # remove ' from string

                    self.expiration_collection.find_one_and_update({"user_id": user.id, "pool_alert": pool_alert}, {
                        '$set': {"user_id": user.id, "pool_alert": pool_alert}}, upsert=True)
                    
                    if pool_alert >= 86400:
                        await conv.send_message(f"Set alert {int(pool_alert/86400)} days before expiration")
                    elif pool_alert >= 3600:
                        await conv.send_message(f"Set alert {int(pool_alert/3600)} hours before expiration")
                    else:
                        await conv.send_message(f"Set alert {int(pool_alert/60)} minutes before expiration")
                        
            elif "delete_a" in str(event.data):
                async with self.tg_client.conversation(event.chat_id) as conv:
                    pool_alert = int(str(event.data).split(" ")[1].replace("'",""))
                    #pool_id = int(str(event.data).split(" ")[2].split("'")[0])  # remove ' from string

                    self.expiration_collection.delete_one({"user_id": user.id, "pool_alert": pool_alert})
                    
                    if pool_alert >= 86400:
                        await conv.send_message(f"Removed alert {int(pool_alert/86400)} days")
                    elif pool_alert >= 3600:
                        await conv.send_message(f"Removed alert {int(pool_alert/3600)} hours")
                    else:
                        await conv.send_message(f"Removed alert {int(pool_alert/60)} minutes")
                    

            elif 'Add alerts' in str(event.data):

                async with self.tg_client.conversation(event.chat_id) as conv:
                    keyboard = [
                        [
                            Button.inline(
                                "3 days", f'set {3*24*60*60}'),
                            Button.inline(
                                "1 day", f'set {24*60*60}'),
                            Button.inline(
                                "12 hrs", f'set {12*60*60}'),
                            Button.inline(
                                "6 hrs", f'set {6*60*60}'),
                            Button.inline(
                                "3 hrs", f'set {3*60*60}'),
                            Button.inline(
                                "1 hr", f'set {1*60*60}'),
                            Button.inline(
                                "15 mins", f'set {15*60}'),
                        ]
                    ]

                    await conv.send_message("Please set alerts:", buttons=keyboard)

            elif 'Edit alerts' in str(event.data):
                async with self.tg_client.conversation(event.chat_id) as conv:
                    
                    alerts = list(self.expiration_collection.find({"user_id":user.id}))
                    keyboard = []
                    msg = ''
                    for idx, alert in enumerate(alerts):
                        if idx < 8:
                            alert["pool_alert"] = int(alert["pool_alert"])
                            if alert["pool_alert"] >= 86400:
                                msg += f'{int(alert["pool_alert"]/86400)} days set on\n'
                                keyboard.append(Button.inline(f'{int(alert["pool_alert"]/86400)} days', f'delete_a {alert["pool_alert"]}'))
                            elif alert["pool_alert"] >= 3600:
                                msg += f'{int(alert["pool_alert"]/3600)} hours set on\n'
                                keyboard.append(Button.inline(f'{int(alert["pool_alert"]/3600)} hrs', f'delete_a {alert["pool_alert"]}'))
                            else:
                                msg += f'{int(alert["pool_alert"]/60)} minutes set on\n'
                                keyboard.append(Button.inline(f'{int(alert["pool_alert"]/60)} mins', f'delete_a {alert["pool_alert"]}'))
                    
                    if len(keyboard):
                        await conv.send_message(f"Choose alerts to delete:\n{msg}", buttons=keyboard)
                    else:
                        await conv.send_message(f"No alerts to delete")
                    #response = await conv.get_response()
                    #logger.info(response)

            elif 'Alerts' in str(event.data):

                async with self.tg_client.conversation(event.chat_id) as conv:

                    if "proposal on" in str(event.data):
                        self.proposal_collection.find_one_and_update({"user_id": user.id}, {
                                                                    '$set': {"user_id": user.id, 'proposal_alert': True}}, upsert=True)
                        await conv.send_message('Proposal alerts set on')

                    if "proposal off" in str(event.data):
                        self.proposal_collection.find_one_and_update({"user_id": user.id}, {
                                                                    '$set': {"user_id": user.id, 'proposal_alert': False}}, upsert=True)
                        await conv.send_message('Proposal alerts set off')

                    if "pool on" in str(event.data):
                        self.pool_collection.find_one_and_update({"user_id": user.id}, {
                                                                '$set': {"user_id": user.id, 'pool_alert': True}}, upsert=True)
                        await conv.send_message('New pool alerts set on')

                    if "pool off" in str(event.data):
                        self.pool_collection.find_one_and_update({"user_id": user.id}, {
                                                                '$set': {"user_id": user.id, 'pool_alert': False}}, upsert=True)
                        await conv.send_message('New pool alerts set off')
                        
                    if "auction on" in str(event.data):
                        self.auction_collection.find_one_and_update({"user_id": user.id}, {
                                                                '$set': {"user_id": user.id, 'auction_alert': True}}, upsert=True)
                        await conv.send_message('New auction alerts set on')

                    if "auction off" in str(event.data):
                        self.auction_collection.find_one_and_update({"user_id": user.id}, {
                                                                '$set': {"user_id": user.id, 'auction_alert': False}}, upsert=True)
                        await conv.send_message('New auction alerts set off')
            else:
                await self.tg_client.send_message(
                    event.chat_id, "Sorry, I don't understand")
                # await conv.send_message('Choose an option:')
                # response = await conv.get_response()
                # logger.info(response)
        except Exception as e:
            logger.error(e)
            await self.tg_client.send_message(
                    event.chat_id, "Sorry, I don't understand")
            
            
    async def edit_coin(self, event):
        user = await event.get_sender()
        token_id = str(event.message.message).replace('/edit_c_', '').replace('_', '-')
        
        coin = self.get_price.get_token(token_id.replace("_", "-"))
        logger.debug(coin)
        async with self.tg_client.conversation(event.chat_id) as conv:
            keyboard = [
                    [
                        Button.inline("📈 Change alert ", f'change_{token_id.replace("-", "_")}'),
                        Button.inline("🗑 Delete ", f'delete_c_{token_id.replace("-", "_")}'),
                    ]
                ]
            setting = self.token_alerts_collection.find_one({"user_id": user.id, "token_id": token_id})
            await conv.send_message(f'Edit:\n{coin["name"]}\n{coin["symbol"].upper()} is ${coin["current_price"]}\nalert: {setting["change_percent"]}% ', buttons=keyboard)

    async def price_alert(self, event):
        keyboard = [
            [
                Button.inline("🚀 Add coin", b'Add coin'),
                Button.inline("💰 Edit coins", b'Edit coins list')
            ]
        ]
        await self.tg_client.send_message(event.chat_id, "Choose an option:", buttons=keyboard)

    async def proposal_alert(self, event):
        keyboard = [
            [
                Button.inline("🔉 Proposal alerts on", b'Alerts proposal on'),
                Button.inline("❌ Proposal alerts off", b'Alerts proposal off')
            ]
        ]
        await self.tg_client.send_message(event.chat_id, "Choose an option:", buttons=keyboard)

    async def pool_alert(self, event):
        keyboard = [
            [
                Button.inline("🔉 Pool alerts on", b'Alerts pool on'),
                Button.inline("❌ Pool alerts off", b'Alerts pool off')
            ]
        ]
        await self.tg_client.send_message(event.chat_id, "Choose an option:", buttons=keyboard)

    async def auction_alert(self, event):
        keyboard = [
            [
                Button.inline("🔉 Auction alerts on", b'Alerts auction on'),
                Button.inline("❌ Auction alerts off", b'Alerts auction off')
            ]
        ]
        await self.tg_client.send_message(event.chat_id, "Choose an option:", buttons=keyboard)
        
    async def pool_exp_alert(self, event):
        keyboard = [
            [
                Button.inline("🚨 Add alerts", b'Add alerts'),
                Button.inline("🗑 Delete alerts", b'Edit alerts')
            ]
        ]
        await self.tg_client.send_message(event.chat_id, "Choose an option:", buttons=keyboard)
        
        
    
    async def profile_settings(self, event):
        user = await event.get_sender()
        groups = self.profiles.find({"user_id":user.id})
        keyboard = []
        
        for group in groups:
            status = "On" if group['notifications'] else "Off"
            keyboard.append([Button.inline(f'{group["title"]}:{status}', f'group_set_{group["id"]}')])
        
        keyboard.append([Button.url("Click here to add to a group", url=f'https://t.me/{os.getenv("TELEGRAM_BOT_NAME")}?startgroup=true')])
        await self.tg_client.send_message(event.chat_id, "Set Group`s and Channel`s notifications:", buttons=keyboard)

    async def chat_handler(self, event):
        logger.debug(event)
        
    async def handler(self, event):
        user = await event.get_sender()
        if type(event.message.peer_id) == types.PeerUser:
            user_dict = user.to_dict()
            user_dict["chat_id"] = event.chat_id
            self.users_collection.find_one_and_update(
                {"id": user.id}, {'$set': user_dict }, upsert=True)
            keyboard = [
                [
                    Button.text("🚀 Price Alerts"),
                    Button.text("📣 New Proposal Alerts",),
                    Button.text("📢 New Pool Alerts"),
                    
                ],
                {
                    Button.text("💸 New Auction Alerts"),
                    Button.text("🚨 Pool Expiration Alerts"),
                    Button.text("Profile")
                }
            ]

            await self.tg_client.send_message(event.chat_id, f"🤖 Hey hey, {user.first_name} , welcome on board!", buttons=keyboard)
        else:
            
            group = await self.tg_client.get_entity(event.message.peer_id)
            group = group.to_dict()
            group["user_id"] = user.id
            group["notifications"] = True
            self.profiles.find_one_and_replace({"user_id":user.id,"id":group["id"]},group,upsert=True)
            await self.tg_client.send_message(event.chat_id, f"✅ ShortFinance bot has been successfully added!\n❗️To activate, open the bot, Main Menu➼Profiles➼ Open a Profile that you wish to use for that group➼Select ON near the group's name")


if __name__ == '__main__':

    # init db connection
    client_mongo = pymongo.MongoClient(f'mongodb://{os.getenv("MONGO_SERVER")}:{os.getenv("MONGO_PORT")}/',
                                       username=os.getenv("MONGO_LOGIN"), password=os.getenv("MONGO_PASS"))

    # save sql session
    bot = TelegramClient('sessions/bot', os.getenv("TELEGRAM_API_ID"), os.getenv(
        "TELEGRAM_API_HASH")).start(bot_token=os.getenv("TELEGRAM_BOT_TOKEN"))
    main_bot = TGmainbot(bot, client_mongo, os.getenv(
        "CACHE_TIME_PRICE_LIST"), os.getenv("CACHE_TIME_PRICE"))
