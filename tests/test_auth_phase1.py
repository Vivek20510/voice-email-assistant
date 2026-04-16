def test_signup_and_status(client):
    signup_response = client.post('/auth/signup', json={'email': 'vivek@example.com', 'password': 'P@ssw0rd'})
    assert signup_response.status_code == 200
    assert signup_response.json['email'] == 'vivek@example.com'

    status_response = client.get('/auth/status')
    assert status_response.status_code == 200
    assert status_response.json['email'] == 'vivek@example.com'


def test_signup_duplicate_email(client):
    first_response = client.post('/auth/signup', json={'email': 'vivek@example.com', 'password': 'P@ssw0rd'})
    assert first_response.status_code == 200

    second_response = client.post('/auth/signup', json={'email': 'vivek@example.com', 'password': 'NewPass123'})
    assert second_response.status_code == 409
    assert second_response.json['error'] == 'Email address already registered.'


def test_login_invalid_credentials(client):
    response = client.post('/auth/login', json={'email': 'unknown@example.com', 'password': 'wrong'})
    assert response.status_code == 401
    assert response.json['error'] == 'Invalid credentials.'


def test_signup_missing_fields(client):
    response = client.post('/auth/signup', json={'email': 'invalid@example.com'})
    assert response.status_code == 400
    assert response.json['error'] == 'Email and password are required.'


def test_login_missing_fields(client):
    response = client.post('/auth/login', json={'password': 'P@ssw0rd'})
    assert response.status_code == 400
    assert response.json['error'] == 'Email and password are required.'


def test_dashboard_requires_login(client):
    response = client.get('/auth/dashboard')
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_logout_clears_session(client):
    client.post('/auth/signup', json={'email': 'vivek@example.com', 'password': 'P@ssw0rd'})
    logout_response = client.get('/auth/logout')
    assert logout_response.status_code == 200

    status_response = client.get('/auth/status')
    assert status_response.status_code == 401
    assert status_response.json['error'] == 'Unauthorized.'
