import os
from db import DB
from web3 import Web3, Account

class Wallet:
    def __init__(self):
        self.db = DB("db/wallets.db")
        self.web3 = Web3(Web3.HTTPProvider(os.getenv("BSC_RPC_URL")))

        if not self.web3.is_connected():
            raise ConnectionError("Unable to connect to the BSC node.")

        self.db.execute_query('''CREATE TABLE IF NOT EXISTS wallets (
                            uid TEXT PRIMARY KEY,
                            private_key TEXT NOT NULL,
                            address TEXT NOT NULL UNIQUE)''')

        self.db.execute_query('''CREATE TABLE IF NOT EXISTS transactions (
                            tx_hash TEXT PRIMARY KEY,
                            uid TEXT NOT NULL,
                            address TEXT NOT NULL,
                            amount DOUBLE NOT NULL)''')

    def createWallet(self, uid):
        if self.db.fetch_one("SELECT * FROM wallets WHERE uid = ?", (uid,)):
            raise ValueError("Wallet already exists for this user.")

        # Create a new wallet
        account = Account.create()
        private_key = account.key.hex()
        address = account.address

        # Store wallet in the database
        self.db.insert("wallets", {"uid": uid, "private_key": private_key, "address": address})

        return {"address": address, "private_key": private_key}

    def getWallet(self, uid):
        wallet = self.db.fetch_one("SELECT address, private_key FROM wallets WHERE uid = ?", (uid,))
        if not wallet:
            return self.createWallet(uid)
        return {"address": wallet[0], "private_key": wallet[1]}

    def getBalance(self, uid):
        wallet = self.getWallet(uid)
        address = wallet["address"]

        # Get the balance in wei and convert to Ether
        balance = self.web3.eth.get_balance(address)
        return self.web3.from_wei(balance, 'ether')

    def withdraw(self, uid, recipientAddress, amount):
        wallet = self.getWallet(uid)
        private_key = wallet["private_key"]
        address = wallet["address"]

        # Get the current balance
        balance = self.getBalance(uid)

        if float(amount) > float(balance):
            raise ValueError("Insufficient funds.")

        # Construct the transaction
        nonce = self.web3.eth.getTransactionCount(address)
        transaction = {
            'nonce': nonce,
            'to': recipientAddress,
            'value': self.web3.toWei(amount, 'ether'),
            'gasPrice': self.web3.toWei('20', 'gwei')
        }

        transaction["gas"] = self.web3.eth.estimateGas(transaction)

        # Sign the transaction
        signed_txn = self.web3.eth.account.sign_transaction(transaction, private_key)

        # Send the transaction
        tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        self.db.insert("transactions", {"tx_hash": tx_hash.hex(), "uid": uid, "address": address, "amount": amount})

        return { tx_hash: tx_hash.hex() }