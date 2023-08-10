import atexit
import datetime
import json
import os
import signal
import sys
import time

import requests
from flask import Flask, jsonify, redirect, render_template, request

from block import Block
from blockchain import Blockchain
from config import *

app = Flask(__name__)


class AppContext:
    def __init__(self):
        self.blockchain = Blockchain()
        self.peers = set()
        self.posts = []


app_context = AppContext()


@app.route('/new_transaction', methods=['POST'])
def new_transaction():
    data = request.json
    author = data.get('author')
    email = data.get('email')
    file = request.files.get('file')
    if not author or not email or not file:
        return 'Invalid transaction data', 400
    tx_data = {'author': author, 'email': email, 'file': file}
    tx_data['timestamp'] = time.time()
    app_context.blockchain.add_transaction(tx_data)
    return 'Success', 200


def create_chain_dump(chain_dump):
    blockchain = Blockchain()
    for idx, block_data in enumerate(chain_dump):
        if idx == 0:
            continue
        block = Block(block_data["index"], block_data["transactions"],
                      block_data["timestamp"], block_data["previous_hash"], block_data["nonce"])
        proof = block_data['hash']
        blockchain.add_block(block, proof)
    return blockchain


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = []
    for block in app_context.blockchain.chain:
        chain_data.append(block.__dict__)
    return jsonify(length=len(chain_data), chain=chain_data, peers=list(app_context.peers))


def save_chain():
    file = os.environ.get('data_file')
    if file is not None:
        with open(file, 'w') as chain_file:
            chain_file.write(json.dumps(get_chain().json))


def exit_from_signal(signum, stack_frame):
    sys.exit(0)


atexit.register(save_chain)
signal.signal(signal.SIGTERM, exit_from_signal)
signal.signal(signal.SIGINT, exit_from_signal)

file = os.environ.get('data_file')
data = None
if file is not None and os.path.exists(file):
    with open(file, 'r') as chain_file:
        raw_data = chain_file.read()
        if raw_data:
            data = json.loads(raw_data)

if data is None:
    app_context.blockchain = Blockchain()
else:
    app_context.blockchain = create_chain_dump(data['chain'])
    app_context.peers.update(data['peers'])


@app.route('/mine', methods=['GET'])
def mine_transactions():
    if not app_context.blockchain.mine():
        return 'No transaction to mine'
    else:
        chain_length = len(app_context.blockchain.chain)
        consensus()
        if chain_length == len(app_context.blockchain.chain):
            announce_new_block(app_context.blockchain.last_block)
        return f'Block #{app_context.blockchain.last_block.index} mined.'


@app.route('/pending_tx')
def get_pending():
    return jsonify(app_context.blockchain.unconfirmed_transactions)


@app.route('/register_node', methods=['POST'])
def register_peers():
    node_address = request.get_json()['node_address']
    if not node_address:
        return 'Invalid data', 404
    app_context.peers.add(node_address)
    return get_chain()


@app.route('/register_with', methods=['POST'])
def register_with_existing_nodes():
    node_address = request.get_json()['node_address']
    if not node_address:
        return 'Invalid data', 404
    data = {'node_address': request.host_url}
    headers = {'Content-Type': 'application/json'}
    response = requests.post(
        node_address + '/register_node', json=data, headers=headers)
    if response.status_code == 200:
        chain_dump = response.json()['chain']
        app_context.blockchain = create_chain_dump(chain_dump)
        app_context.peers.update(response.json()['peers'])
        return 'Registration successful', 200
    else:
        return response.content, response.status_code


def consensus():
    longest_chain = None
    current_len = len(app_context.blockchain.chain)
    for node in app_context.peers:
        response = requests.get(f'{node}/chain')
        if response.status_code == 200:
            length = response.json()['length']
            chain = response.json()['chain']
            if length > current_len and app_context.blockchain.chain_validity(chain):
                current_len = length
                longest_chain = chain
    if longest_chain:
        app_context.blockchain = create_chain_dump(longest_chain)
        return True
    return False


@app.route('/add_block', methods=['POST'])
def verify_and_add_block():
    block_data = request.get_json()
    block = Block(block_data['index'], block_data['transactions'],
                  block_data['timestamp'], block_data['previous_hash'])
    proof = block_data['hash']
    try:
        app_context.blockchain.add_block(block, proof)
    except ValueError as e:
        return 'The block was discarded by node: ' + str(e), 400
    return 'Block added to the chain', 200


def announce_new_block(block):
    for peer in app_context.peers:
        url = f'{peer}/add_block'
        headers = {'Content-Type': 'application/json'}
        try:
            requests.post(url, json=block.__dict__, headers=headers)
        except requests.RequestException as e:
            print(f'Error announcing new block to {url}: {e}')


def fetch_posts():
    get_chain_address = f'{CONNECTED_NODE_ADDRESS}/chain'
    try:
        response = requests.get(get_chain_address)
    except requests.RequestException as e:
        print(f'Error fetching posts: {e}')
        return
    if response.status_code == 200:
        content = []
        chain = json.loads(response.content)
        for block in chain['chain']:
            for tx in block['transactions']:
                tx['index'] = block['index']
                tx['hash'] = block['previous_hash']
                content.append(tx)
        app_context.posts = sorted(
            content, key=lambda k: k['timestamp'], reverse=True)


@app.route('/')
def index():
    fetch_posts()
    return render_template('index.html', title='Blockchain', posts=app_context.posts, node_address=CONNECTED_NODE_ADDRESS, readable_time=timestamp_to_string)


def timestamp_to_string(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime('%H:%M')


@app.route('/submit', methods=['POST'])
def submit():
    author = request.form.get('author')
    email = request.form.get('email')
    file = request.files.get('file')
    post_object = {'author': author, 'email': email, 'file': file.filename}
    new_tx_address = f'{CONNECTED_NODE_ADDRESS}/new_transaction'
    headers = {'Content-Type': 'application/json'}
    try:
        requests.post(new_tx_address, json=post_object, headers=headers)
    except requests.RequestException as e:
        print(f'Error submitting new transaction to {new_tx_address}: {e}')
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
