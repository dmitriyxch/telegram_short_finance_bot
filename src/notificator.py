import asyncio
from telethon import TelegramClient, types
import pymongo
from pathlib import Path
from loguru import logger
import datetime
from dotenv import load_dotenv
import os
import price
from pathlib import Path

env_file = '.env' if os.path.isfile('.env') else 'bot.env'
logger.info(f'env_file: {env_file}')
dotenv_path = Path(env_file)
load_dotenv(dotenv_path=dotenv_path)


class Notificator:

    def __init__(self, tg_client: TelegramClient, mongo_client: pymongo.MongoClient, cache_time_price_list, cache_time_price):
        # mongo init
        self.mongo_db = mongo_client
        self.db = self.mongo_db["telegram_db"]
        self.users_collection = self.db["users"]
        self.token_alerts_collection = self.db["token_alerts"]
        self.proposal_collection = self.db["proposal_alerts"]
        self.pool_collection = self.db["pool_alerts"]
        self.profiles = self.db["profiles"]
        self.expiration_collection = self.db["expiration_alerts"]

        self.get_price = price.Price(
            self.mongo_db, cache_time_price_list=cache_time_price_list, cache_time_price=cache_time_price)

        self.tg_client = tg_client

    async def check_price_hike(self):
        all_alerts = list(self.token_alerts_collection.find({}))

        # update data batch 100
        ids = []
        for alert in all_alerts:
            ids.append(alert["token_id"])
            if len(ids) == 100:
                self.get_price.load_market_data(ids, "usd")
                ids = []
        if len(ids):
            self.get_price.load_market_data(ids, "usd")

        for alert in all_alerts:
            token = self.get_price.get_token(alert["token_id"])
            diff = token['current_price'] - alert["last_price"]
            percent = round(diff/(alert["last_price"]/100), 2)

            if abs(percent) >= abs(alert["change_percent"]):
                logger.debug(percent)
                setting = self.users_collection.find_one(
                    {"id": alert["user_id"]})
                if percent > 0:
                    icon = '🚀'
                else:
                    icon = '🔻️'
                
                groups = list(self.profiles.find({"user_id":setting["id"], "notifications":True}))
                if len(groups):
                    for group in groups:
                        
                        ent = group["id"]
                        if group["_"] == 'Channel':
                            ent = types.PeerChannel(group["id"])
                        elif group["_"] == 'Chat':
                            ent = types.PeerChat(group["id"])
                            
                        await self.tg_client.send_message(ent, f"{icon} <a href ='https://www.coingecko.com/en/coins/{token['id']}'>{token['symbol'].upper()}</a> price changed {percent}%! Current price ${token['current_price']}", parse_mode="html", link_preview=False)
                else:
                    await self.tg_client.send_message(setting["id"], f"{icon} <a href ='https://www.coingecko.com/en/coins/{token['id']}'>{token['symbol'].upper()}</a> price changed {percent}%! Current price ${token['current_price']}", parse_mode="html", link_preview=False)
                self.token_alerts_collection.find_one_and_update({"token_id": alert["token_id"], "user_id": alert["user_id"]}, {
                                                                 "$set": {"last_price": token['current_price'], "last_update": datetime.datetime.utcnow().isoformat()}})



if __name__ == '__main__':

    # init db connection
    client_mongo = pymongo.MongoClient(f'mongodb://{os.getenv("MONGO_SERVER")}:{os.getenv("MONGO_PORT")}/',
                                       username=os.getenv("MONGO_LOGIN"), password=os.getenv("MONGO_PASS"))

    # save sql session
    bot = TelegramClient('sessions/bot_notificator', os.getenv("TELEGRAM_API_ID"), os.getenv(
        "TELEGRAM_API_HASH")).start(bot_token=os.getenv("TELEGRAM_BOT_TOKEN"))
    notificator = Notificator(bot, client_mongo, os.getenv(
        "CACHE_TIME_PRICE_LIST"), os.getenv("CACHE_TIME_PRICE"))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(notificator.check_price_hike())
    # main_bot.start()
