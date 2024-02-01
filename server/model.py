from __future__ import print_function

import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.layers import Dense, Activation, Dropout, Input
from tensorflow.keras.models import load_model, Model
import tensorflow_hub as hub

import time
import numpy as np
import re
import html
import ast
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def connect_gmail():
    """
    Establishes connection with Google Cloud Platform
    and Google Account.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('server/token.json'):
        creds = Credentials.from_authorized_user_file('server/token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'server/credentials.json', SCOPES)
            creds = flow.run_local_server(port=3000)
        # Save the credentials for the next run
        with open('server/token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=creds)
    return service

def get_metadata_from_message(msg):
    metadata = {}

    payload = msg['payload']
    headers = payload.get("headers")

    metadata['message-id'] = msg['id']
    metadata['preview'] = html.unescape(msg.get('snippet'))

    if 'labelIds' in msg:
        metadata['labels'] = msg['labelIds']
    else:
        metadata['labels'] = []

    if 'IMPORTANT' in metadata['labels']:
        metadata['type'] = 'important'
    else:
        metadata['type'] = 'unimportant'

    if headers:
        for header in headers:
            name = header.get("name")
            value = header.get("value")
            if name.lower() == 'from':
                metadata['author'] = re.sub(r'(.*)\s<(.*)>', r'\1',
                                            value)  # based on alphamail-v0.2 helpers.py and https://docs.python.org/3/library/re.html
                metadata['author-address'] = re.sub(r'(.*)\s<(.*)>', r'\2',
                                                    value)  # for context on r operator, see https://stackoverflow.com/questions/26163798/using-r-with-string-literals-in-python
            if name.lower() == "to": metadata['to'] = value
            if name.lower() == "subject": metadata['subject'] = html.unescape(value)
            if name.lower() == "date": metadata['date'] = value
    return metadata

def batch_request_threads_from_ids(service, ids, format='metadata', user_id='me'):
    print("batch_request_threads_from_ids start")
    data = []
    while len(ids) > 0:
        batch = service.new_batch_http_request()
        if len(ids) > 100:
            batch_ids = ids[:100]
            ids = ids[100:]
            time.sleep(4)  # slow rate limit to 15000 queries per minute (250 per sec) for gmail api
            print('Remaining: ' + str(len(ids)))
        else:
            batch_ids = ids
            ids = []
        for id in batch_ids:
            batch.add(service.users().threads().get(userId=user_id, id=id, format=format))
        batch.execute()
        for res in list(batch._responses.values()):  # extract data from batch response
            data.append(ast.literal_eval(res[1].decode('UTF-8')))
            # TODO understand different string formats like UTF-8
    return data

def get_metadata_from_thread(thread):
    metadata = {'thread-id': thread['id'], 'labels': [], 'type': 'unimportant', 'preview': '', 'subject': '', 'msg-count': 0, 'authors': [], 'date-rec': '', 'date-sent': ''}
    message_metadata = []

    for msg in thread['messages']:
        msg_metadata = get_metadata_from_message(msg)
        message_metadata.append(msg_metadata)
        for label in msg_metadata['labels']:
            if label not in metadata['labels']:
                metadata['labels'].append(label)
        if 'SENT' not in msg_metadata['labels']:
            metadata['date-rec'] = msg_metadata['date']
        else:
            metadata['date-sent'] = msg_metadata['date']
        if msg_metadata['author'] not in metadata['authors']:
            metadata['authors'].append(msg_metadata['author'])

    if 'preview' in message_metadata[-1]:
        metadata['preview'] = ['preview']
    else:
        print('no preview', thread['id'])
        metadata['preview'] = 'no preview'
    if 'subject' in message_metadata[0]:
        metadata['subject'] = message_metadata[0]['subject']
    else:
        print('no preview', thread['id'])
        metadata['subject'] = 'no subject'
    metadata['msg-count'] = len(message_metadata)

    metadata['messages'] = message_metadata
    return metadata

def get_metadata_from_threads(threads):
    start_time = time.time()
    metadata = []
    for thread in threads:
        metadata.append(get_metadata_from_thread(thread))
    print(f'get_metadata_from_thread execution time: {(time.time() - start_time):.3f} seconds')
    return metadata

def model3():
    """
    GPT-3 based embeddings model for email classification
    """
    input = Input(shape=(1536,))
    dropout = Dropout(0.05)(input)
    output = Dense(1, activation='sigmoid')(dropout)
    model = Model(inputs=[input], outputs=output)

    return model

def get_embedding(text, model='text-embedding-ada-002'):
    """
    Returns OpenAI text model embedding or batch of embeddings
    """
    return openai.Embedding.create(input=text, model=model)['data']

def get_embeddings(dataset):
    embeddings = []
    batch = []
    for i, text in enumerate(dataset):
        batch.append(text[0])
        if (i % 100 == 99 or i == len(dataset)-1) and len(batch) != 0:
            # print("embedding progress:", i+1, "of", len(dataset))
            # print(batch)
            for embedding in get_embedding(batch):
                embeddings.append(embedding['embedding'])
            batch = []

    return np.array(embeddings)

def get_msg_headlines(metadata):
    dataset = []
    for msg_metadata in metadata:
        msg_headline = f'{msg_metadata["authors"]}: {msg_metadata["subject"]}'
        dataset.append([msg_headline])
    dataset = np.array(dataset)
    return dataset

# some inspiration from https://dref360.github.io/keras-web/
class Model:
    def __init__(self):
        self.model = None

    def initialize(self, model):
        self.model = model
        self.model.compile(optimizer='adam', loss='binary_crossentropy')

    def load(self, file_name, file_path='server/model/saved_models'):
        self.model = keras.models.load_model(f'{file_path}/{file_name}',
                                             custom_objects={'KerasLayer': hub.KerasLayer})

    def generate_embeddings(self, x):
        return get_embeddings(x)

    def predict(self, predict_x, embeddings=False):
        if embeddings:
            predict_x_embeddings = self.generate_embeddings(predict_x)
            return self.model.predict(predict_x_embeddings), predict_x_embeddings
        return self.model.predict(predict_x)