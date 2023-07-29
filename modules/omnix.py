from seleniumwire import webdriver
from bs4 import BeautifulSoup
from eth_account import Account

import time
import random
from typing import Optional, Union

from loguru import logger
from web3 import Web3
from eth_account import Account as EthereumAccount
from web3.exceptions import TransactionNotFound


from config import RPC, OMNIX_CONTRACT, OMNIX_ABI, CHAIN_ID
from settings import BRIDGE_CHAIN, SLEEP_BRIDGE_MIN, SLEEP_BRIDGE_MAX
from eth_typing import Address, ChecksumAddress


class Omnix:
    def __init__(self, private_key: str) -> None:
        self.private_key = private_key
        self.explorer = "https://optimistic.etherscan.io/tx/"

        self.w3 = Web3(Web3.HTTPProvider(random.choice(RPC)))
        self.account = EthereumAccount.from_key(private_key)
        self.address = self.account.address

    def get_contract(self, token_address: Optional[Union[Address, ChecksumAddress]], abi=None):
        contract = self.w3.eth.contract(address=token_address, abi=abi)
        return contract

    def get_balance(self):
        balance = self.w3.eth.get_balance(self.address)
        return balance

    def wait_until_tx_finished(self, hash: str, max_wait_time=180):
        start_time = time.time()
        while True:
            try:
                receipts = self.w3.eth.get_transaction_receipt(hash)
                status = receipts.get("status")
                if status == 1:
                    logger.success(f"[{self.address}] {self.explorer}{hash} successfully!")
                    return True
                elif status is None:
                    time.sleep(0.3)
                elif status != 1:
                    logger.error(f"[{self.address}] {self.explorer}{hash} transaction failed!")
                    return False
            except TransactionNotFound:
                if time.time() - start_time > max_wait_time:
                    print(f'FAILED TX: {hash}')
                    return False
                time.sleep(1)

    def sign(self, transaction):
        signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
        return signed_txn

    def send_raw_transaction(self, signed_txn):
        txn_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return txn_hash

    def get_lz_fee(self, chain_id, nft_id):
        contract = self.get_contract(Web3.to_checksum_address(OMNIX_CONTRACT), OMNIX_ABI)

        get_fee = contract.functions.estimateSendBatchFee(
            chain_id,
            self.address,
            [nft_id],
            False,
            "0x0001000000000000000000000000000000000000000000000000000000000003f7a0"
        ).call()

        fee = get_fee[0]
        return fee

    def get_owned_nfts_from_explorer(self, ACCOUNTS):
        """Returns a list of NFTs owned by this address."""
        account = Account.from_key(ACCOUNTS)
        address = account.address

        url = f'https://optimistic.etherscan.io/tokentxns-nft?a={address}'
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument('--headless')
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Get the full HTML content of the page
        html_content = driver.page_source

        # Create a BeautifulSoup object and find all 'tr' elements
        soup = BeautifulSoup(html_content, 'html.parser')
        tr_elements = soup.find_all('tr')

        # Initialize an empty list to store the ids of the blocks
        block_ids = []

        # Filter out the blocks based on the conditions
        for tr in tr_elements:
            tds = tr.find_all('td')

            # Check if the block contains "OMNIA"
            contains_omnia = 'OMNIA' in tds[-1].text if tds else False

            # Check if the "from" address is "0x0000000000000000000000000000000000000000"
            from_address = tds[4].text.strip() if len(tds) > 4 else None
            from_address_is_zero = from_address == "Null: 0x000…000"

            # If both conditions are met, get the id of the block and add it to the list
            if contains_omnia and from_address_is_zero:
                block_id = tds[7].text.strip() if len(tds) > 7 else None
                if block_id:
                    block_ids.append(block_id)

        driver.quit()

        return block_ids
    def mint(self, quantity: int, contract):
        logger.info(f"[{self.address}] Start minting {quantity} nft!")

        tx_data = {
            "from": self.address,
            "gasPrice": self.w3.eth.gas_price,
            "nonce": self.w3.eth.get_transaction_count(self.address),
            "value": 0
        }

        transaction = contract.functions.mint(quantity).build_transaction(tx_data)
        signed_tx = self.sign(transaction)
        txn_hash = self.send_raw_transaction(signed_tx)
        self.wait_until_tx_finished(txn_hash.hex())
        return txn_hash

    def chose_nft_id(self, nft_id_list, quantity: int):
        chosen_ids = random.sample(nft_id_list, quantity)
        return chosen_ids

    def get_nft_id(self, txn_hash: str, quantity: int):
        receipts = self.w3.eth.get_transaction_receipt(txn_hash)

        nft_id_list = [int(i['topics'][3].hex(), 0) for i in receipts["logs"][0:quantity]]
        return nft_id_list

    def mint_and_bridge(self, quantity: int):
        contract = self.get_contract(Web3.to_checksum_address(OMNIX_CONTRACT), OMNIX_ABI)

        txn_hash = self.mint(quantity, contract)
        nft_id_list = self.get_nft_id(txn_hash.hex(), quantity)

        for j, nft_id in enumerate(nft_id_list):
            chain = random.choice(BRIDGE_CHAIN)
            chain_id = CHAIN_ID[chain]

            logger.info(f"[{self.address}] Bridge nft [{nft_id}] to {chain.title()}")

            tx_data = {
                "from": self.address,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": self.w3.eth.get_transaction_count(self.address),
                "value": self.get_lz_fee(chain_id, nft_id)
            }

            transaction = contract.functions.sendFrom(
                self.address,
                chain_id,
                self.address,
                nft_id,
                self.address,
                "0x0000000000000000000000000000000000000000",
                "0x0001000000000000000000000000000000000000000000000000000000000003f7a0"
            ).build_transaction(tx_data)

            signed_tx = self.sign(transaction)
            txn_hash = self.send_raw_transaction(signed_tx)
            self.wait_until_tx_finished(txn_hash.hex())

            if j + 1 < len(nft_id_list):
                time.sleep(random.uniform(SLEEP_BRIDGE_MIN, SLEEP_BRIDGE_MAX))

    def bridge_with_no_mint(self, quantity: int, nft_id_list):
        contract = self.get_contract(Web3.to_checksum_address(OMNIX_CONTRACT), OMNIX_ABI)

        nft_id_list = self.chose_nft_id(nft_id_list, quantity)
        logger.info(f"[{self.address}] Will bridge nft {quantity} times")

        for j, nft_id in enumerate(nft_id_list):
            chain = random.choice(BRIDGE_CHAIN)
            chain_id = CHAIN_ID[chain]

            logger.info(f"[{self.address}] Bridge nft [{nft_id}] to {chain.title()}")

            tx_data = {
                "from": self.address,
                "gasPrice": self.w3.eth.gas_price,
                "nonce": self.w3.eth.get_transaction_count(self.address),
                "value": self.get_lz_fee(chain_id, nft_id)
            }

            transaction = contract.functions.sendFrom(
                self.address,
                chain_id,
                self.address,
                nft_id,
                self.address,
                "0x0000000000000000000000000000000000000000",
                "0x0001000000000000000000000000000000000000000000000000000000000003f7a0"
            ).build_transaction(tx_data)

            signed_tx = self.sign(transaction)
            txn_hash = self.send_raw_transaction(signed_tx)
            self.wait_until_tx_finished(txn_hash.hex())

            if j + 1 < len(nft_id_list):
                time.sleep(random.uniform(SLEEP_BRIDGE_MIN, SLEEP_BRIDGE_MAX))
