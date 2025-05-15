from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import datetime
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather_data.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class WeatherRequestLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.String(10), nullable=False)
    end_date = db.Column(db.String(10), nullable=False)
    request_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    api_response_status = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<WeatherRequestLog {self.latitude}, {self.longitude}, {self.start_date} to {self.end_date}>'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}), 200

@app.route('/api/weather', methods=['POST'])
def get_weather_data():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    lat = data.get('latitude')
    lon = data.get('longitude')
    start_date_str = data.get('startDate')
    end_date_str = data.get('endDate')
    start_time_str = data.get('startTime')
    end_time_str = data.get('endTime')


    if None in [lat, lon, start_date_str, end_date_str]: # startTime and endTime are optional
        return jsonify({"error": "Missing data: latitude, longitude, startDate, or endDate"}), 400

    try:
        datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
        if datetime.datetime.strptime(start_date_str, '%Y-%m-%d') > datetime.datetime.strptime(end_date_str, '%Y-%m-%d'):
             return jsonify({"error": "Start date cannot be after end date"}), 400
        if start_time_str: # Validate if provided
            datetime.datetime.strptime(start_time_str, '%H:%M')
        if end_time_str:   # Validate if provided
            datetime.datetime.strptime(end_time_str, '%H:%M')
        if start_time_str and end_time_str and start_time_str >= end_time_str:
            return jsonify({"error": "Start time must be before end time"}), 400

    except ValueError:
        return jsonify({"error": "Invalid date or time format. Please use YYYY-MM-DD and HH:MM"}), 400

    open_meteo_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "hourly": "temperature_2m",
        "timezone": "auto",
        "temperature_unit": "celsius"
    }

    api_response_status_log = "N/A"
    actual_weather_info = {"temperature_readings": []}

    try:
        response = requests.get(open_meteo_url, params=params, timeout=10)
        response.raise_for_status()
        
        open_meteo_data = response.json()
        api_response_status_log = f"Success ({response.status_code})"

        if 'hourly' in open_meteo_data and 'time' in open_meteo_data['hourly'] and 'temperature_2m' in open_meteo_data['hourly']:
            times = open_meteo_data['hourly']['time']
            temperatures = open_meteo_data['hourly']['temperature_2m']
            
            for i in range(len(times)):
                temp_value = temperatures[i] if temperatures[i] is not None else "N/A"
                actual_weather_info["temperature_readings"].append({
                    "time": times[i],
                    "temp_c": temp_value
                })
        else:
            app.logger.warning("Open-Meteo response missing expected hourly data structure.")
            api_response_status_log = "Success but unexpected data structure"
            actual_weather_info["temperature_readings"].append({"error": "Data format from Open-Meteo was not as expected."})

    except requests.exceptions.HTTPError as http_err:
        app.logger.error(f"HTTP error occurred: {http_err} - {response.text if response else 'No response text'}")
        api_response_status_log = f"HTTP Error ({response.status_code if response else 'N/A'})"
        return jsonify({"error": f"Error fetching weather data from provider: {response.status_code if response else 'N/A'}", "details": response.text if response else "No response object"}), response.status_code if response else 500
    except requests.exceptions.ConnectionError as conn_err:
        app.logger.error(f"Connection error occurred: {conn_err}")
        api_response_status_log = "Connection Error"
        return jsonify({"error": "Could not connect to weather data provider."}), 503
    except requests.exceptions.Timeout as timeout_err:
        app.logger.error(f"Timeout error occurred: {timeout_err}")
        api_response_status_log = "Timeout Error"
        return jsonify({"error": "Request to weather data provider timed out."}), 504
    except requests.exceptions.RequestException as req_err:
        app.logger.error(f"An error occurred with the weather API request: {req_err}")
        api_response_status_log = "Request Exception"
        return jsonify({"error": "An unexpected error occurred while fetching weather data."}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during Open-Meteo call or processing: {e}")
        api_response_status_log = "Unexpected processing error"
        return jsonify({"error": "An internal error occurred while processing weather data."}), 500

    try:
        new_log_entry = WeatherRequestLog(
            latitude=lat,
            longitude=lon,
            start_date=start_date_str,
            end_date=end_date_str,
            api_response_status=api_response_status_log
        )
        db.session.add(new_log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error: {e}")

    app.logger.info(f"Processed weather request for Lat: {lat}, Lon: {lon}, Dates: {start_date_str} to {end_date_str}, Times: {start_time_str} to {end_time_str}")

    # Update the data_received to include the times
    data_for_response = {
        "latitude": lat,
        "longitude": lon,
        "startDate": start_date_str,
        "endDate": end_date_str,
        "startTime": start_time_str,
        "endTime": end_time_str
    }

    return jsonify({
        "message": "Weather data retrieved successfully from Open-Meteo." if "Success" in api_response_status_log else "Weather data request processed, check details.",
        "data_received": data_for_response, # Pass back the full request including times
        "weather_info": actual_weather_info
    }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)