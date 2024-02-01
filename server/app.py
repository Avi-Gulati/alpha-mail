# app.py
from flask import Flask
from flask_restful import Api
from flask_cors import CORS
from importance import ImportanceChecker

app = Flask(__name__)
CORS(app)
api = Api(app)

api.add_resource(ImportanceChecker, '/importance')

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5009)
