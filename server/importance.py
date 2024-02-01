from flask import request
from flask_restful import Resource
import model
import numpy as np

service = model.connect_gmail()
importance_model = model.Model()
importance_model.load('model_gpt_230418_v1')
importance_model.model.summary()

class ImportanceChecker(Resource):
    def get(self):
        return {'message': 'Hello from Flask-RESTful!'}

    def post(self):
        print('hi2')
        data = request.get_json()
        print('hi3')
        headlines = model.get_msg_headlines(model.get_metadata_from_threads(model.batch_request_threads_from_ids(service, data)))
        response = importance_model.predict(headlines, embeddings=True)[0]
        return {'response': response.flatten().tolist()}
