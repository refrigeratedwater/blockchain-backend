import time

import requests

from block import Block
from config import *


class Blockchain:
    def __init__(self, chain=None):
        self.unconfirmed_transactions = []
        self.chain = chain
        if self.chain is None:
            self.chain = []
            self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(0, [], 0, '0')
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def proof_of_work(block):
        block.nonce = 0

        computed_hash = block.compute_hash()
        while not computed_hash.startswith('0' * DIFFICULTY):
            block.nonce += 1
            computed_hash = block.compute_hash()

        return computed_hash

    def add_block(self, block, proof):
        previous_hash = self.last_block.hash

        if previous_hash != block.previous_hash:
            return False

        if not Blockchain.is_valid_proof(block, proof):
            return False

        block.hash = proof
        self.chain.append(block)
        return True

    @classmethod
    def is_valid_proof(cls, block, block_hash):
        return block_hash.startswith('0' * DIFFICULTY) and block_hash == block.compute_hash()

    def add_transaction(self, transaction):
        self.unconfirmed_transactions.append(transaction)

    def mine(self):
        if not self.unconfirmed_transactions:
            return False

        last_block = self.last_block
        new_block = Block(index=last_block.index + 1, transactions=self.unconfirmed_transactions,
                          timestamp=time.time(), previous_hash=last_block.hash)

        proof = self.proof_of_work(new_block)
        self.add_block(new_block, proof)

        self.unconfirmed_transactions = []
        return True

    def chain_validity(cls, chain):
        previous_hash = ''

        for block in chain:
            block_hash = block.hash
            delattr(block, 'hash')

            if not cls.is_valid_proof(block, block.hash) or previous_hash != block.previous_hash:
                return False

            block.hash, previous_hash = block_hash, block_hash

        return True