from datetime import datetime, timedelta
from pycoingecko import CoinGeckoAPI
import requests
from loguru import logger
import pymongo


class Price:

    def __init__(self, mongo_db: pymongo.MongoClient, cache_time_price_list, cache_time_price):
        self.cg = CoinGeckoAPI()
        #self.cache = cache = FaaSCacheDict(default_ttl=600)
        self.db = mongo_db["telegram_db"]
        self.coin_list = self.db["coin_list"]
        self.coin_price = self.db["coin_price"]

        self.cache_time_price_list = cache_time_price_list
        self.cache_time_price = cache_time_price

    # caching api results in mongo, easy to debug and share with others bots clones
    def get_coin_list(self, ticker: str, basic_currency: str = "usd"):
        # check cache
        if self.coin_list.count_documents({"exp_date": {"$gte": datetime.utcnow().isoformat()}}) > 0:
            logger.debug(f'Searching for {ticker} in cache')
            all_coins = list(self.coin_list.find({}))
        else:
            logger.debug(f'Searching for {ticker} in api')
            self.coin_list.delete_many({})
            all_coins = self.cg.get_coins_list(vs_currency=basic_currency)

            # write cache in mongo
            for idx, coin in enumerate(all_coins):
                all_coins[idx]["exp_date"] = (datetime.utcnow(
                ) + timedelta(seconds=int(self.cache_time_price_list))).isoformat()
            self.coin_list.insert_many(all_coins)
        return all_coins

    def get_token(self, id):
        logger.debug(f'Searching for {id} in cache')
        return self.coin_price.find_one({"id": id})
    
    def get_price(self, id, basic_currency):
        if self.coin_price.count_documents({"id": id, "exp_date": {"$gte": datetime.utcnow().isoformat()}}) > 0:
            logger.debug(f'Searching for {id} in cache')
            price = self.coin_price.find_one({"id": id})
        """else:
            logger.debug(f'Searching for {id} in api')
            self.coin_price.delete_one({"id":id })
            prices = self.cg.get_coins_markets(ids = id, vs_currencies=basic_currency)
            for price in prices:
                price["exp_date"] = (datetime.utcnow() + timedelta(seconds=int(self.cache_time_price))).isoformat()
                self.coin_price.insert_one(price)"""

        return price

    def load_market_data(self, ids, basic_currency):
        logger.debug(f'Searching for {ids} in api')
        prices = self.cg.get_coins_markets(ids=ids, vs_currency=basic_currency)
        for price in prices:
            price["exp_date"] = (
                datetime.utcnow() + timedelta(seconds=int(self.cache_time_price))).isoformat()
            self.coin_price.replace_one(
                {"id": price["id"]}, dict(price), upsert=True)

        return prices
    # search for a coin by name

    def search_by_ticker(self, ticker: str, basic_currency: str = "usd"):
        coin_list = []
        prepare_coin_list = []
        try:
            all_coins = self.get_coin_list(ticker, basic_currency)
            # get all coins with the same ticker
            for coin_item in all_coins:
                if str(coin_item['symbol']).lower() == ticker.lower() or ticker.lower() in str(coin_item['symbol']).lower():
                    coin_list.append(coin_item)

            # sort list by dict value
            coin_list = sorted(coin_list, key=lambda k: len(
                k['symbol']), reverse=False)

            ids = []
            for x in coin_list[:100]:
                ids.append(x['id'])

            coin_list_new = self.load_market_data(ids, basic_currency)
            coin_list_new = sorted(
                coin_list_new, key=lambda k: float(str(k['market_cap']).replace("None","0")), reverse=True)
            # add price to list
            for idx, coin in enumerate(coin_list_new):
                if idx < 9:  # hard coded limit for list, to prevent spamming api
                    prepare_coin_list.append(coin_list_new[idx])
                    """
                    price = self.get_price(coin['id'], basic_currency)
                    logger.debug(price)
                    if coin['id'] in price and 'current_price' in price[coin['id']]:
                        coin_list[idx]["price"] = price[coin['id']]['current_price']"""

        except requests.exceptions.HTTPError as e:
            logger.error(e)

        except ValueError as e:
            logger.error(e)

        return prepare_coin_list
