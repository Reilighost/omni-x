import random
import time

from modules import Omnix
from config import ACCOUNTS
from settings import RANDOM_WALLET, SLEEP_TO, SLEEP_FROM, IS_SLEEP, AMOUNT_MIN, AMOUNT_MAX, MINT_NEW_NFTS


def main():
    if RANDOM_WALLET:
        random.shuffle(ACCOUNTS)

    for j, key in enumerate(ACCOUNTS):
        if MINT_NEW_NFTS is True:
            omnix = Omnix(key)
            omnix.mint_and_bridge(int(random.uniform(AMOUNT_MIN, AMOUNT_MAX)))

            if j + 1 < len(ACCOUNTS) and IS_SLEEP:
                time.sleep(random.randint(SLEEP_FROM, SLEEP_TO))
        if MINT_NEW_NFTS is False:
            omnix = Omnix(key)
            nft_ids = omnix.get_owned_nfts_from_explorer(ACCOUNTS[j])  # Get list of NFT ids
            nft_ids_int = [int(id) for id in nft_ids]
            print(nft_ids)
            quantity = int(random.uniform(AMOUNT_MIN, AMOUNT_MAX))
            omnix.bridge_with_no_mint(quantity, nft_ids_int)

            if j + 1 < len(ACCOUNTS) and IS_SLEEP:
                time.sleep(random.randint(SLEEP_FROM, SLEEP_TO))


if __name__ == '__main__':
    print("Subscribe to me – https://t.me/sybilwave")
    print("Also subscribe to BBC™ couse I mode this shit, my chanel – https://t.me/CryptoBub_ble")
    main()
    print("Subscribe to me – https://t.me/sybilwave")
    print("Also subscribe to BBC™ couse I mode this shit, my chanel – https://t.me/CryptoBub_ble")
