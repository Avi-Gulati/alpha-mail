from flask import Flask, request
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

class MessageResource(Resource):
    def post(self):
        data = request.get_json(force=True)
        return {'received_data': data}

api.add_resource(MessageResource, '/message')

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5004)
