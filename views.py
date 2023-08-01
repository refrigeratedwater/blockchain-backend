import datetime
import json

import requests
from flask import redirect, render_template, request

from app import app
from config import *

posts = []


def fetch_posts():
    get_chain_address = '{}/chain'.format(CONNECTED_NODE_ADDRESS)
    response = requests.get(get_chain_address)
    if response.status_code == 200:
        content = []
        chain = json.loads(response.content)
        for block in chain['chain']:
            for tx in block['transactions']:
                tx['index'] = block['index']
                tx['hash'] = block['previous_hash']
                content.append(tx)

        global posts
        posts = sorted(content, key=lambda k: k['timestamp'], reverse=True)


@app.route('/')
def index():
    fetch_posts()
    return render_template('index.html', title='Blockchain', posts=posts, node_address=CONNECTED_NODE_ADDRESS, readable_time=timestamp_to_string)


def timestamp_to_string(epoch):
    return datetime.datetime.fromtimestamp(epoch).strftime('%H:%M')


@app.route('submit', methods=['POST'])
def submit():
    post_content = request.form['content']
    author = request.form['author']

    post_object = {'author': author, 'content': post_content}

    new_tx_address = '{}/new_transaction'.format(CONNECTED_NODE_ADDRESS)

    requests.post(new_tx_address, json=post_object, headers={
                  'Contene_Type': 'application/json'})

    return redirect('/')
