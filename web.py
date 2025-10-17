from flask import Flask, render_template, jsonify, request
import requests
import random
import string

app = Flask(__name__)

BASE_URL = "https://api.mail.tm"

# store all created accounts in memory
# structure: {email: {"password": "...", "token": "..."}}
accounts = {}

# helper: random string generator
def random_string(length=8):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

# create a new Mail.tm account and return email + password + token
def create_account():
    # 1. get available domains
    domains = requests.get(f"{BASE_URL}/domains").json()["hydra:member"]
    domain = domains[0]["domain"]

    email = f"{random_string()}@{domain}"
    password = random_string(12)

    acc = {"address": email, "password": password}

    # 2. create account
    requests.post(f"{BASE_URL}/accounts", json=acc)

    # 3. get token
    token_res = requests.post(f"{BASE_URL}/token", json=acc).json()
    token = token_res.get("token")

    if not token:
        raise Exception("Failed to get token")

    # save account in memory
    accounts[email] = {"password": password, "token": token}

    return {"email": email, "password": password, "token": token}


def refresh_token(email):
    """If token is expired, re-login using email+password"""
    if email not in accounts:
        return None

    creds = {"address": email, "password": accounts[email]["password"]}
    token_res = requests.post(f"{BASE_URL}/token", json=creds).json()
    token = token_res.get("token")

    if token:
        accounts[email]["token"] = token
        return token
    return None


@app.route('/')
def home():
    return render_template("index.html")


@app.route('/generate')
def generate():
    try:
        account = create_account()
        return jsonify(account)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/inbox', methods=['POST'])
def inbox():
    try:
        email = request.json.get("email")
        if email not in accounts:
            return jsonify({"error": "Unknown email"}), 400

        token = accounts[email]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/messages", headers=headers)

        # if token expired, refresh and retry
        if r.status_code == 401:
            token = refresh_token(email)
            if not token:
                return jsonify({"error": "Re-login failed"}), 500
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.get(f"{BASE_URL}/messages", headers=headers)

        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/message/<msg_id>', methods=['POST'])
def message(msg_id):
    try:
        email = request.json.get("email")
        if email not in accounts:
            return jsonify({"error": "Unknown email"}), 400

        token = accounts[email]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)

        # if token expired, refresh and retry
        if r.status_code == 401:
            token = refresh_token(email)
            if not token:
                return jsonify({"error": "Re-login failed"}), 500
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers)

        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
