def test_email_routes_require_login(client):
    list_response = client.get("/email/list")
    assert list_response.status_code == 401
    assert list_response.json["error"] == "Unauthorized."

    send_response = client.post(
        "/email/send", json={"to": "test@example.com", "subject": "Hello"}
    )
    assert send_response.status_code == 401
    assert send_response.json["error"] == "Unauthorized."

    read_response = client.get("/email/read/1")
    assert read_response.status_code == 401
    assert read_response.json["error"] == "Unauthorized."


def test_email_route_stubs_with_session(client):
    client.post(
        "/auth/signup", json={"email": "user@example.com", "password": "SecurePass123"}
    )

    send_response = client.post(
        "/email/send", json={"to": "test@example.com", "subject": "Hello"}
    )
    assert send_response.status_code == 200
    assert send_response.json == {"status": "queued"}

    list_response = client.get("/email/list")
    assert list_response.status_code == 200
    assert list_response.json == {"emails": []}

    read_response = client.get("/email/read/1")
    assert read_response.status_code == 501
    assert read_response.json["error"] == "not implemented"
