import time
import requests
import random

from urllib.parse import urlparse
from datetime import datetime

from block import Block
from config import *


class Blockchain:
    def __init__(self, chain=None):
        self.unconfirmed_transactions = []
        self.chain = chain
        self.nodes = set()
        if self.chain is None:
            self.chain = []
            self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(0, [], 0, '0')
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        last_block = [0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.is_valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None

        max_length = self.chain

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def proof_of_work(block):
        block.nonce = 0

        computed_hash = block.compute_hash()
        while not computed_hash.startswith('0' * DIFFICULTY):
            block.nonce = random.randint(BOUNDARY[0], BOUNDARY[1])
            computed_hash = block.compute_hash()

        return computed_hash

    def get_cid(self, cid):
        for block in self.chain:
            for tx in block.transactions:
                if tx.get('file_info').get('current') == cid:
                    return tx

        return None

    def get_all_authors(self):
        authors = set()
        for block in self.chain:
            for tx in block.transactions:
                authors.add(tx.get('author'))

        return list(authors)

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
                          timestamp=convert_time(time.time()), previous_hash=last_block.hash)

        proof = self.proof_of_work(new_block)
        self.add_block(new_block, proof)

        self.unconfirmed_transactions = []
        return True
