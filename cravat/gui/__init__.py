from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello World!</p>"


def start_server(interface, port):
    from waitress import serve
    serve(app, host=interface, port=port)