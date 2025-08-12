from flask import Flask, jsonify

app = Flask(__name__)


@app.route('/health')
def health():
    return jsonify({"status": "ok", "service": "user-service"})


@app.route('/users')
def users():
    return jsonify({"users": []})


if __name__ == '__main__':
    app.run(debug=True, port=5001)
