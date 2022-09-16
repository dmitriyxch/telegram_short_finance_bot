import asyncio
from telethon import TelegramClient, types
import pymongo
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import os
import web3
from pathlib import Path
import json
import time

env_file = '../.env' if os.path.isfile('../.env') else 'bot.env'
logger.info(f'env_file: {env_file}')
dotenv_path = Path(env_file)
load_dotenv(dotenv_path=dotenv_path)


class EventsChecker:

    def __init__(self, tg_client: TelegramClient, mongo_client: pymongo.MongoClient, node_url, committee_contract, istr_contract, auction_contract):
        # mongo init
        self.mongo_db = mongo_client
        self.db = self.mongo_db["telegram_db"]
        self.users_collection = self.db["users"]
        self.token_alerts_collection = self.db["token_alerts"]
        self.proposal_collection = self.db["proposal_alerts"]
        self.pool_collection = self.db["pool_alerts"]
        self.auction_collection = self.db["auction_alerts"]
        self.expiration_collection = self.db["expiration_alerts"]
        self.notifications_collection = self.db["notifications"]
        self.profiles = self.db["profiles"]
        self.tg_client = tg_client

        self.w3 = web3.Web3(web3.HTTPProvider(node_url))
        self.contract_proposal = self.w3.eth.contract(address=self.w3.toChecksumAddress(committee_contract),
                                                  abi=json.loads(Path('abi/ICommittee.json').read_text())["abi"])
        
        self.contract_str_pool = self.w3.eth.contract(address=self.w3.toChecksumAddress(istr_contract),
                                                  abi=json.loads(Path('abi/IStrPool.json').read_text())["abi"])
        
        self.contract_auction = self.w3.eth.contract(address=self.w3.toChecksumAddress(auction_contract),
                                                  abi=json.loads(Path('abi/IAuctionHall.json').read_text())["abi"])
    async def loop(self):
        while True:
            await self.check_new_expiration()
            await self.check_new_proposal()
            await self.check_new_auction()
            await self.check_new_pool()
            logger.debug('cycle')
            time.sleep(5)
    
    async def send_entity_message(self,entity_id, message, parse_mode="html", link_preview=False):
        groups = list(self.profiles.find({"user_id":entity_id, "notifications":True}))
        if len(groups):
            for group in groups:
                ent = group["id"]
                if group["_"] == 'Channel':
                    ent = types.PeerChannel(group["id"])
                elif group["_"] == 'Chat':
                    ent = types.PeerChat(group["id"])
                    
                await self.tg_client.send_message(ent,message,parse_mode = parse_mode,link_preview = link_preview)
        else:
            await self.tg_client.send_message(ent,message,parse_mode = parse_mode,link_preview = link_preview)
    
    #work well, get only closest 1 pool to expiration
    async def check_new_expiration(self):
        pool = self.contract_str_pool.functions.getInfo().call()
        if len(pool):
            end_block = pool[7]
            seconds = (end_block - self.w3.eth.blockNumber) * 14 #hardcode for eth network
            all_alerts = list(self.expiration_collection.find({}))
            
            for alert in all_alerts:
                if seconds <= int(alert["pool_alert"]):
                    if self.notifications_collection.count_documents({"type":"check_new_expiration", "id" : pool[8]}) == 0: #check if we sent notification
                        logger.debug(alert)
                        await self.send_entity_message(alert["user_id"], f"Poll expires soon <a href='https://app.shorter.finance/pools/{pool[8]}'>{pool[8]}</a>", parse_mode="html", link_preview=False)
                        self.notifications_collection.insert_one({"type":"check_new_expiration", "id" : pool[8]})
                    

    #work well
    async def check_new_proposal(self):
        transferEvents = self.contract_proposal.events.PoolProposalCreated.createFilter(
            fromBlock=self.w3.eth.blockNumber, toBlock=self.w3.eth.blockNumber)
        entries = transferEvents.get_all_entries()
        if len(entries):
            all_alerts = list(self.proposal_collection.find({}))
            #print(list(entries))
            for tr_event in entries:
                for alert in all_alerts:
                    if alert["proposal_alert"] == True:
                        if self.notifications_collection.count_documents({"type":"check_new_proposal", "id" : tr_event['args']['proposalId']}) == 0: #check if we sent alert
                            logger.debug(alert)
                            await self.send_entity_message(alert["user_id"], f"New Proposal was created <a href='https://app.shorter.finance/governance/proposals/{tr_event['args']['proposalId']}'>{tr_event['args']['proposalId']}</a>", parse_mode="html", link_preview=False)
                            self.notifications_collection.insert_one({"type":"check_new_proposal", "id" : tr_event['args']['proposalId']})
                            
    
    #works well
    async def check_new_auction(self):
        transferEvents = self.contract_auction.events.AuctionInitiated.createFilter(
            fromBlock=self.w3.eth.blockNumber, toBlock=self.w3.eth.blockNumber)
        entries = transferEvents.get_all_entries()
        if len(entries):
            logger.debug(entries)
            all_alerts = list(self.auction_collection.find({}))
            #print(list(entries))
            for tr_event in entries:
                for alert in all_alerts:
                    if alert["proposal_alert"] == True:
                        if self.notifications_collection.count_documents({"type":"check_new_auction", "id" : tr_event['args']['positionAddr']}) == 0: #check if we sent alert
                            logger.debug(alert)
                            await self.send_entity_message(alert["user_id"], f"New Auction was started <a href='https://app.shorter.finance/liquidations/{tr_event['args']['positionAddr']}'>{tr_event['args']['positionAddr']}</a>", parse_mode="html", link_preview=False)
                            self.notifications_collection.insert_one({"type":"check_new_auction", "id" : tr_event['args']['positionAddr']})

    #works well
    async def check_new_pool(self):
        transferEvents = self.contract_proposal.events.ProposalStatusChanged.createFilter(
            fromBlock=self.w3.eth.blockNumber, toBlock=self.w3.eth.blockNumber)
        entries = transferEvents.get_all_entries()
                
        if len(entries):
            #print(list(entries))
            for tr_event in entries:
                if tr_event["args"]["ps"] == 4:
                    all_alerts = list(self.pool_collection.find({}))
                    for alert in all_alerts:
                        if alert["pool_alert"] == True:
                            if self.notifications_collection.count_documents({"type":"check_new_pool", "id" : tr_event['args']['proposalId']}) == 0: #check if we sent alert
                                logger.debug(alert)
                                await self.send_entity_message(alert["user_id"], f"New Pool was created <a href='https://app.shorter.finance/pools/{tr_event['args']['proposalId']}'>{tr_event['args']['proposalId']}</a>", parse_mode="html", link_preview=False)
                                self.notifications_collection.insert_one({"type":"check_new_pool", "id" : tr_event['args']['proposalId']}) 


if __name__ == '__main__':

    # init db connection
    client_mongo = pymongo.MongoClient(f'mongodb://{os.getenv("MONGO_SERVER")}:{os.getenv("MONGO_PORT")}/',
                                       username=os.getenv("MONGO_LOGIN"), password=os.getenv("MONGO_PASS"))

    # save sql session
    bot = TelegramClient('sessions/bot_events', os.getenv("TELEGRAM_API_ID"), os.getenv(
        "TELEGRAM_API_HASH")).start(bot_token=os.getenv("TELEGRAM_BOT_TOKEN"))
    event = EventsChecker(bot, client_mongo, os.getenv("W3_NODE_URL"), os.getenv("COMMITTEE_TOKEN"), os.getenv("STRPOOL_TOKEN"), os.getenv("AUCTION_HALL_TOKEN"))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(event.loop())
    # main_bot.start()
