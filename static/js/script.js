document.addEventListener('DOMContentLoaded', function () {
    var map = L.map('map').setView([39.8283, -98.5795], 4);
    var marker;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18,
    }).addTo(map);

    var selectedLat = null;
    var selectedLng = null;
    var selectedCoordsDisplay = document.getElementById('selectedCoords');

    map.on('click', function(e) {
        selectedLat = e.latlng.lat;
        selectedLng = e.latlng.lng;

        if (marker) {
            map.removeLayer(marker);
        }
        marker = L.marker([selectedLat, selectedLng]).addTo(map);
        marker.bindPopup("Selected Location<br>Lat: " + selectedLat.toFixed(4) + "<br>Lon: " + selectedLng.toFixed(4)).openPopup();
        selectedCoordsDisplay.textContent = `Selected: Lat: ${selectedLat.toFixed(4)}, Lon: ${selectedLng.toFixed(4)}`;
    });

    var getWeatherButton = document.getElementById('getWeatherButton');
    var startDateInput = document.getElementById('startDate');
    var endDateInput = document.getElementById('endDate');
    var startTimeInput = document.getElementById('startTime');
    var endTimeInput = document.getElementById('endTime');
    var infoDiv = document.getElementById('info');

    getWeatherButton.addEventListener('click', function() {
        var startDateStr = startDateInput.value;
        var endDateStr = endDateInput.value;
        var startTimeStr = startTimeInput.value;
        var endTimeStr = endTimeInput.value;

        // Validations ---
        if (!selectedLat || !selectedLng) {
            infoDiv.innerHTML = '<p style="color: red;">Please select a location on the map first.</p>';
            alert('Please select a location on the map first.');
            return;
        }

        if (!startDateStr || !endDateStr) {
            infoDiv.innerHTML = '<p style="color: red;">Please select both a start and an end date.</p>';
            alert('Please select both a start and an end date.');
            return;
        }

        if (new Date(startDateStr) > new Date(endDateStr)) {
            infoDiv.innerHTML = '<p style="color: red;">Start date cannot be after end date.</p>';
            alert('Start date cannot be after end date.');
            return;
        }

        if (startDateStr === endDateStr && startTimeStr && endTimeStr && startTimeStr >= endTimeStr) {
            infoDiv.innerHTML = '<p style="color: red;">Start time must be before end time on the same day.</p>';
            alert('Start time must be before end time on the same day.');
            return;
        }
        
        const now = new Date();
        // Normalize 'now' to have 0 seconds and 0 milliseconds
        now.setSeconds(0, 0); 

        let selectedEndDateTime = new Date(endDateStr);

        if (endTimeStr) {
            const [endHour, endMinute] = endTimeStr.split(':').map(Number);
            selectedEndDateTime.setHours(endHour, endMinute, 0, 0); // Use 0 for seconds and ms for comparison
        } else {
            // If no end time is specified, it implies the user wants data up to the end of the selected endDate.
            // So, the point to validate against is the very end of that day.
            selectedEndDateTime.setHours(23, 59, 0, 0); // Compare against the last minute of the day
        }

        if (selectedEndDateTime > now) {
            infoDiv.innerHTML = '<p style="color: red;">The selected end date and time cannot be later than the current moment.</p>';
            alert('The selected end date and time cannot be later than the current moment.');
            return;
        }


        infoDiv.innerHTML = '<p>Fetching weather data...</p>';

        fetch('/api/weather', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                latitude: selectedLat,
                longitude: selectedLng,
                startDate: startDateStr,
                endDate: endDateStr,
                startTime: startTimeStr || null,
                endTime: endTimeStr || null
            })
        })
        .then(response => {
            const statusCode = response.status;
            return response.json().then(data => ({ data, statusCode }));
        })
        .then(({ data, statusCode }) => {
            console.log('Response Status:', statusCode);
            console.log('Response Data:', data);
            infoDiv.innerHTML = '';

            if (data.message) {
                const messageEl = document.createElement('p');
                messageEl.style.fontStyle = 'italic';
                messageEl.textContent = data.message;
                if (statusCode >= 400) {
                    messageEl.style.color = 'red';
                }
                infoDiv.appendChild(messageEl);
            }
            
            if (data.error) {
                const errorEl = document.createElement('p');
                errorEl.style.color = 'red';
                errorEl.textContent = `Error: ${data.error}`;
                if(data.details) {
                     const detailsEl = document.createElement('p');
                     detailsEl.style.color = 'red';
                     detailsEl.style.fontSize = '0.9em';
                     detailsEl.textContent = `Details: ${data.details}`;
                     errorEl.appendChild(detailsEl);
                }
                infoDiv.appendChild(errorEl);
                return; 
            }

            if (data.data_received) {
                const requestDetailsHeader = document.createElement('h3');
                requestDetailsHeader.textContent = 'Request Details:';
                infoDiv.appendChild(requestDetailsHeader);

                let locationText = `<strong>Location:</strong> Latitude: ${data.data_received.latitude.toFixed(4)}, Longitude: ${data.data_received.longitude.toFixed(4)}`;
                const locationEl = document.createElement('p');
                locationEl.innerHTML = locationText;
                infoDiv.appendChild(locationEl);

                let dateRangeText = `<strong>Date Range:</strong> ${data.data_received.startDate} to ${data.data_received.endDate}`;
                if (data.data_received.startTime || data.data_received.endTime) {
                    dateRangeText += ` (Times: ${data.data_received.startTime || 'Any'} to ${data.data_received.endTime || 'Any'})`;
                }
                const dateRangeEl = document.createElement('p');
                dateRangeEl.innerHTML = dateRangeText;
                infoDiv.appendChild(dateRangeEl);
            }

            if (data.weather_info && data.weather_info.temperature_readings) {
                const weatherHeader = document.createElement('h3');
                weatherHeader.textContent = 'Hourly Temperature Readings:';
                infoDiv.appendChild(weatherHeader);

                let filteredReadings = data.weather_info.temperature_readings;
                if (startTimeStr || endTimeStr) {
                    const startHour = startTimeStr ? parseInt(startTimeStr.split(':')[0]) : 0;
                    const startMinute = startTimeStr ? parseInt(startTimeStr.split(':')[1]) : 0;
                    const endHour = endTimeStr ? parseInt(endTimeStr.split(':')[0]) : 23;
                    const endMinute = endTimeStr ? parseInt(endTimeStr.split(':')[1]) : 59;

                    filteredReadings = data.weather_info.temperature_readings.filter(reading => {
                        if (reading.error) return true; 
                        const readingTime = new Date(reading.time);
                        const readingHour = readingTime.getHours();
                        const readingMinute = readingTime.getMinutes();

                        let afterStartTime = true;
                        if (startTimeStr) {
                            if (readingHour < startHour) afterStartTime = false;
                            if (readingHour === startHour && readingMinute < startMinute) afterStartTime = false;
                        }

                        let beforeEndTime = true;
                        if (endTimeStr) {
                            if (readingHour > endHour) beforeEndTime = false;
                            if (readingHour === endHour && readingMinute > endMinute) beforeEndTime = false;
                        }
                        return afterStartTime && beforeEndTime;
                    });
                }

                if (filteredReadings.length > 0 && !filteredReadings[0].error) {
                    const ul = document.createElement('ul');
                    ul.style.listStyleType = 'none';
                    ul.style.paddingLeft = '0';

                    filteredReadings.forEach(reading => {
                        const li = document.createElement('li');
                        li.style.border = '1px solid #eee';
                        li.style.padding = '10px';
                        li.style.marginBottom = '10px';
                        li.style.borderRadius = '4px';

                        const timeEl = document.createElement('p');
                        const dateObj = new Date(reading.time);
                        const formattedTime = `${dateObj.toLocaleDateString()} ${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
                        timeEl.innerHTML = `<strong>Time:</strong> ${formattedTime}`;
                        li.appendChild(timeEl);

                        const tempEl = document.createElement('p');
                        tempEl.innerHTML = `Temperature: ${reading.temp_c !== undefined ? reading.temp_c + ' °C' : 'N/A'}`;
                        li.appendChild(tempEl);

                        ul.appendChild(li);
                    });
                    infoDiv.appendChild(ul);
                } else if (filteredReadings.length > 0 && filteredReadings[0].error) {
                    const errorMsgEl = document.createElement('p');
                    errorMsgEl.style.color = 'orange';
                    errorMsgEl.textContent = filteredReadings[0].error;
                    infoDiv.appendChild(errorMsgEl);
                } else {
                    const noReadingsEl = document.createElement('p');
                    noReadingsEl.textContent = 'No temperature readings available for the selected criteria (including time filter).';
                    infoDiv.appendChild(noReadingsEl);
                }
            } else if (statusCode < 400) {
                 const noWeatherInfoEl = document.createElement('p');
                 noWeatherInfoEl.textContent = 'Weather information block is missing or incomplete in the response.';
                 infoDiv.appendChild(noWeatherInfoEl);
            }
        })
        .catch((error) => {
            console.error('Fetch Error:', error);
            infoDiv.innerHTML = `<p style="color: red;">An application error occurred: ${error.message}</p>`;
        });
    });
});