from flask import Flask, redirect, request, session, url_for # type: ignore
from github import Github, Auth

import requests
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
client_id = "" #sarthak'sid
client_secret = "" #sarthak'ssecret
# client_id = " " #your id
# client_secret = " " #your secret
redirect_uri = "http://127.0.0.1:5000/callback"

auth_url = "https://github.com/login/oauth/authorize"
tok_url = "https://github.com/login/oauth/access_token"
userid = "https://api.github.com/user"

@app.route('/')
def home():
    code = """
    <h1>Welcome to the GitHub OAuth App</h1>
    <p><a href='/login'>Log in with GitHub</a></p>
    """
    return code


@app.route('/login')
def login():
    return redirect(f"{auth_url}?client_id={client_id}&redirect_uri={redirect_uri}&scope=repo,user")


@app.route('/callback')
def callback():
    code = request.args.get("code")
    if not code:
        return "Error: Missing authorization code"

    token_response = requests.post(
        tok_url,
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )
    token_json = token_response.json()
    access_token = token_json.get("access_token")

    if not access_token:
        return "Error: Could not retrieve access token"

    session['access_token'] = access_token
    headers = {"Authorization": f"token {access_token}"}
    user_response = requests.get(userid, headers=headers)
    user_data = user_response.json()

    return f"<h1>Welcome, {user_data['login']}</h1><p><a href='/repos'>View your repositories</a></p>"

@app.route('/repos')
def repos():
    access_token = session.get("access_token")
    if not access_token:
        return redirect(url_for("login"))

    
    headers = {"Authorization": f"token {access_token}"}
    repos_response = requests.get("https://api.github.com/user/repos", headers=headers)
    repos_data = repos_response.json()

    repo_list = "<ul>" + "".join([f"<li>{repo['name']}</li>" for repo in repos_data]) + "</ul>"
    return f"<h1>Your Repositories</h1>{repo_list}"

    
    # repo_list = "<ul>"
    # for repo in repos_data:
    #     name = repo.get('name', 'No Name')
    # #     description = repo.get('description', 'No description provided')
    # #     stars = repo.get('stargazers_count', 0)
    #     repo_list = f"<li>{name}</li>"
    # #     repo_list += f"<li><strong>{name}</strong> - {stars} ⭐<br>{description}</li>"
    # repo_list += "</ul>"

if __name__ == "__main__":
    app.run(debug=True)
