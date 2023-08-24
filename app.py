import atexit
import json
import os
import signal
import sys
import time

import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import ipfshttpclient
from block import Block
from blockchain import Blockchain
from config import *

app = Flask(__name__)
CORS(app)


class AppContext:
    def __init__(self):
        self.blockchain = Blockchain()
        self.posts = []


app_context = AppContext()


def connect_to_ipfs():
    try:
        return ipfshttpclient.connect()
    except ipfshttpclient.exceptions.ConnectionError as e:
        print(e)
        return None


def add_to_ipfs(file):
    api = connect_to_ipfs()
    if api:
        content = api.add(file)

        return content['Hash'], content['Name']


def get_from_ipfs(cid):
    api = connect_to_ipfs()
    if api:
        return api.cat(cid)


@app.route('/add/transaction', methods=['POST'])
def new_transaction():
    author = request.form.get('author')
    email = request.form.get('email')
    file = request.files.get('file')

    if not author:
        return 'Invalid transaction data! Author is missing', 400
    if not email:
        return 'Invalid transaction data! Email is missing', 400
    if not file:
        return 'Invalid transaction data! File is missing', 400

    file_cid, file_name = add_to_ipfs(file)

    if file_cid and file_name:

        file_ext = file_name.rsplit('.', 1)[-1]
        tx_data = {'author': author, 'email': email, 'file name': file.filename,
                   'file': file_cid, 'ext': file_ext, 'timestamp': time.time()}
        app_context.blockchain.add_transaction(tx_data)

        return jsonify('Success'), 200
    else:
        return 'File upload has failed!', 500


@app.route('/get/file/<cid>', methods=['GET'])
def get_file(cid):
    content = get_from_ipfs(cid)

    tx = app_context.blockchain.get_transaction(cid)
    if not tx:
        return 'CID not found', 404

    file_ext = tx['ext']

    ext_to_mime = {
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }

    if content and file_ext in ext_to_mime:
        response = Response(content, content_type=ext_to_mime[file_ext])
        response.headers[
            'Content-Disposition'] = f'attachment; filename=downloaded_file.{file_ext}'
        return response
    else:
        return 'Faailed to retrieve file', 415


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
    return jsonify(length=len(chain_data), chain=chain_data, nodes=list(app_context.blockchain.nodes))


DATA_FILE = "./data_file/data_file.json"


def save_chain():
    try:
        with open(DATA_FILE, 'w') as chain_file:
            chain_data = get_chain().json
            chain_data['nodes'] = list(app_context.blockchain.nodes)
            chain_file.write(json.dumps(chain_data))
    except Exception as e:
        print(f"Error saving chain data: {e}")


def exit_from_signal(signum, stack_frame):
    sys.exit(0)


atexit.register(save_chain)
signal.signal(signal.SIGTERM, exit_from_signal)
signal.signal(signal.SIGINT, exit_from_signal)

data = None
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r') as chain_file:
            raw_data = chain_file.read()
            data = json.loads(raw_data)
    except Exception as e:
        print(f"Error reading data file: {e}")

if data is None:
    app_context.blockchain = Blockchain()
else:
    try:
        app_context.blockchain = create_chain_dump(data['chain'])
        app_context.blockchain.nodes.update(data['nodes'])
    except Exception as e:
        print(f"Error creating blockchain from data: {e}")
        app_context.blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine_transactions():
    if not app_context.blockchain.mine():
        return jsonify(status='failure', message='No transaction to mine')
    else:
        chain_length = len(app_context.blockchain.chain)
        consensus()
        if chain_length == len(app_context.blockchain.chain):
            announce_new_block(app_context.blockchain.last_block)
        return jsonify(status='success', message=f'Block #{app_context.blockchain.last_block.index} mined.', minedBlockIndex=app_context.blockchain.last_block.index)


@app.route('/pending/tx', methods=['GET'])
def get_pending():
    return jsonify(app_context.blockchain.unconfirmed_transactions)


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.json

    nodes = values.get('nodes')
    if nodes is None:
        return 'Error: Supply a valid list of nodes', 400

    for node in nodes:
        app_context.blockchain.register_node(node)

    response = {
        'message': 'New node added',
        'total_nodes': list(app_context.blockchain.nodes)
    }

    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    longest_chain = None
    current_len = len(app_context.blockchain.chain)
    for node in app_context.blockchain.nodes:
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


@app.route('/add/block', methods=['POST'])
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
    for peer in app_context.blockchain.nodes:
        url = f'{peer}/add/block'
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


if __name__ == '__main__':

    app.run(debug=True)

    # load balancer
    # app.run(port=5001, debug=True)
