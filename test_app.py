import unittest
import json
from unittest.mock import patch, MagicMock
import datetime

# Ensure the app and db can be imported.
# If test_app.py is in the same directory as app.py:
from app import app, db, WeatherRequestLog

class BaseTestCase(unittest.TestCase):
    def setUp(self):
        """Set up for each test."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Use in-memory DB for tests
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        self.app_context = app.app_context()
        self.app_context.push() # Push an application context
        
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        """Clean up after each test."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop() # Pop the application context

class TestRoutes(BaseTestCase):

    def test_index_page(self):
        """Test the index page loads."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Interactive Weather Map', response.data) # Check for a known string from index.html

class TestWeatherAPI(BaseTestCase):

    def _get_mock_open_meteo_success_response(self):
        return {
            "latitude": 35.0,
            "longitude": -80.0,
            "hourly": {
                "time": ["2023-01-01T00:00", "2023-01-01T01:00"],
                "temperature_2m": [10.0, 10.5]
            }
        }

    def _get_mock_open_meteo_malformed_response(self):
        return { # Missing 'hourly' key
            "latitude": 35.0,
            "longitude": -80.0
        }

    @patch('app.requests.get') # Mock requests.get specifically in app module
    def test_get_weather_success(self, mock_requests_get):
        """Test successful weather data retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._get_mock_open_meteo_success_response()
        mock_response.text = json.dumps(self._get_mock_open_meteo_success_response())
        mock_requests_get.return_value = mock_response

        payload = {
            "latitude": 35.7796,
            "longitude": -78.7811,
            "startDate": "2023-01-01",
            "endDate": "2023-01-01",
            "startTime": "00:00",
            "endTime": "01:00"
        }
        response = self.client.post('/api/weather', json=payload)
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('Weather data retrieved successfully', data['message'])
        self.assertIn('weather_info', data)
        self.assertIn('temperature_readings', data['weather_info'])
        self.assertEqual(len(data['weather_info']['temperature_readings']), 2)
        self.assertEqual(data['weather_info']['temperature_readings'][0]['temp_c'], 10.0)

        # Check if data was logged to the database
        log_entry = WeatherRequestLog.query.first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.latitude, payload['latitude'])
        self.assertIn("Success (200)", log_entry.api_response_status)

    def test_get_weather_missing_params(self):
        """Test API with missing parameters."""
        payload = {
            "latitude": 35.7796,
            # longitude is missing
            "startDate": "2023-01-01",
            "endDate": "2023-01-01"
        }
        response = self.client.post('/api/weather', json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('Missing data', data['error'])

    def test_get_weather_invalid_date_format(self):
        """Test API with invalid date format."""
        payload = {
            "latitude": 35.7796,
            "longitude": -78.7811,
            "startDate": "2023/01/01", # Invalid format
            "endDate": "2023-01-01"
        }
        response = self.client.post('/api/weather', json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('Invalid date or time format', data['error'])

    def test_get_weather_start_date_after_end_date(self):
        payload = {
            "latitude": 35.0, "longitude": -80.0,
            "startDate": "2023-01-02", "endDate": "2023-01-01"
        }
        response = self.client.post('/api/weather', json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Start date cannot be after end date", data['error'])

    def test_get_weather_start_time_after_end_time_same_day(self):
        payload = {
            "latitude": 35.0, "longitude": -80.0,
            "startDate": "2023-01-01", "endDate": "2023-01-01",
            "startTime": "10:00", "endTime": "09:00"
        }
        response = self.client.post('/api/weather', json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Start time must be before end time", data['error']) # Error message from app.py

    @patch('app.requests.get')
    def test_get_weather_open_meteo_http_error(self, mock_requests_get):
        """Test when Open-Meteo API returns an HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 400 # Example: Bad request to Open-Meteo
        mock_response.json.return_value = {"error": "API error reason"}
        mock_response.text = '{"error": "API error reason", "reason": "Invalid parameters for Open-Meteo"}'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_requests_get.return_value = mock_response
        
        payload = {
            "latitude": 35.0, "longitude": -80.0,
            "startDate": "2023-01-01", "endDate": "2023-01-01"
        }
        response = self.client.post('/api/weather', json=payload)
        
        self.assertEqual(response.status_code, 400) # The status code API returns
        data = response.get_json()
        self.assertIn("Error fetching weather data from provider", data['error'])
        self.assertIn("Invalid parameters for Open-Meteo", data['details'])

        log_entry = WeatherRequestLog.query.first()
        self.assertIsNotNone(log_entry)
        self.assertIn("HTTP Error (400)", log_entry.api_response_status)


    @patch('app.requests.get')
    def test_get_weather_open_meteo_connection_error(self, mock_requests_get):
        """Test when there's a connection error to Open-Meteo."""
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        payload = {
            "latitude": 35.0, "longitude": -80.0,
            "startDate": "2023-01-01", "endDate": "2023-01-01"
        }
        response = self.client.post('/api/weather', json=payload)
        self.assertEqual(response.status_code, 503) # Service Unavailable
        data = response.get_json()
        self.assertIn("Could not connect to weather data provider", data['error'])

        log_entry = WeatherRequestLog.query.first()
        self.assertIsNotNone(log_entry)
        self.assertEqual("Connection Error", log_entry.api_response_status)

    @patch('app.requests.get')
    def test_get_weather_open_meteo_timeout_error(self, mock_requests_get):
        """Test when the request to Open-Meteo times out."""
        mock_requests_get.side_effect = requests.exceptions.Timeout("Request timed out")

        payload = {
            "latitude": 35.0, "longitude": -80.0,
            "startDate": "2023-01-01", "endDate": "2023-01-01"
        }
        response = self.client.post('/api/weather', json=payload)
        self.assertEqual(response.status_code, 504) # Gateway Timeout
        data = response.get_json()
        self.assertIn("Request to weather data provider timed out", data['error'])
        
        log_entry = WeatherRequestLog.query.first()
        self.assertIsNotNone(log_entry)
        self.assertEqual("Timeout Error", log_entry.api_response_status)

    @patch('app.requests.get')
    def test_get_weather_open_meteo_malformed_data(self, mock_requests_get):
        """Test successful API call but unexpected data structure from Open-Meteo."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._get_mock_open_meteo_malformed_response() # Missing 'hourly'
        mock_requests_get.return_value = mock_response

        payload = {
            "latitude": 35.0, "longitude": -80.0,
            "startDate": "2023-01-01", "endDate": "2023-01-01"
        }
        response = self.client.post('/api/weather', json=payload)
        self.assertEqual(response.status_code, 200) # API call was successful
        data = response.get_json()
        self.assertIn("weather_info", data)
        # Check for the specific error message put in this case
        self.assertTrue(any(item.get("error") == "Data format from Open-Meteo was not as expected" for item in data['weather_info']['temperature_readings']))
        
        log_entry = WeatherRequestLog.query.first()
        self.assertIsNotNone(log_entry)
        self.assertIn("Success but unexpected data structure", log_entry.api_response_status)


# Run the tests from the command line
if __name__ == '__main__':
    import requests 
    unittest.main()