from flask import Flask, redirect, request, session, url_for, render_template
import requests
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# GitHub OAuth configuration
client_id = "Ov23liAvKwVKlJkoty1K"
client_secret = "2dfec260a3df780a715b2c5971fb26b9c6fac773"
redirect_uri = "http://127.0.0.1:5000/callback"

# GitHub API endpoints
auth_url = "https://github.com/login/oauth/authorize"
token_url = "https://github.com/login/oauth/access_token"
api_url = "https://api.github.com"

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    auth_params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'repo,user'
    }
    auth_url_with_params = f"https://github.com/login/oauth/authorize?client_id={auth_params['client_id']}&redirect_uri={auth_params['redirect_uri']}&scope={auth_params['scope']}"
    return redirect(auth_url_with_params)

@app.route('/callback')
def callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for('home'))

    response = requests.post(
        token_url,
        headers={"Accept": "application/json"},
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return redirect(url_for('home'))

    session['access_token'] = access_token
    user_response = requests.get(
        f"{api_url}/user",
        headers={"Authorization": f"token {access_token}"}
    )
    user_data = user_response.json()
    
    return redirect(url_for('repositories'))

@app.route('/repositories')
def repositories():
    if 'access_token' not in session:
        return redirect(url_for('login'))

    try:
        headers = {"Authorization": f"token {session['access_token']}"}
        repos_response = requests.get(f"{api_url}/user/repos", headers=headers)
        
        if repos_response.status_code != 200:
            return redirect(url_for('home'))
        
        repos_data = repos_response.json()
        
        repositories = [{
            'name': repo['name'],
            'full_name': repo['full_name'],
            'description': repo['description'],
            'language': repo['language'],
            'stars': repo['stargazers_count'],
            'url': repo['html_url']
        } for repo in repos_data]
        
        return render_template('repositories.html', repositories=repositories)
    
    except Exception:
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)