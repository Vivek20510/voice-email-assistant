def test_summarize_route_returns_summary(client):
    response = client.post('/nlp/summarize', json={'text': 'This is a test email body.'})
    assert response.status_code == 200
    assert 'summary' in response.json
    assert isinstance(response.json['summary'], str)


def test_suggest_route_returns_suggestions(client):
    response = client.post('/nlp/suggest', json={'text': 'Please help with scheduling.'})
    assert response.status_code == 200
    assert 'suggestions' in response.json
    assert isinstance(response.json['suggestions'], list)


def test_nlp_route_validation(client):
    response = client.post('/nlp/summarize', json={})
    assert response.status_code == 400
    assert response.json['error'] == 'Text is required.'
