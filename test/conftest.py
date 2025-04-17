# /marble-api/tests/test_data_request.py
import httpx
from datetime import datetime

# Replace this with your actual server's IP and port
BASE_URL = "http://127.0.0.1:8000/v1"

def test_valid_data_request():
    payload = {
        "start_date": "1990-01-01T00:00:00",
        "end_date": "2024-01-01T00:00:00",
        "latitude": "37.7749",
        "longitude": "-122.899',
        "username": "user123",
        "title": "Test Request",
        "fname": "John",
        "lname": "Doe",
        "email": "john.doe@example.com",
        "geometry": "Point",
        "myFile": None,
        "variables": None,
        "models": None,
        "path": "/some/path",
        "input": None,
        "link": None
    }

    response = httpx.post(f"{BASE_URL}/data-publish-request", json=payload)
    print(response.status_code)
    print(response.text)  # This will print out the error message
    assert response.status_code == 200
    json_data = response.json()

    # Instead of checking for "message", check for the presence of the "id" field
    assert "id" in json_data  # Ensure that the returned data has an "id" field
    assert json_data["username"] == "user123"