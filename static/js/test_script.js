function validateDateTimeSelection(startDateStr, endDateStr, startTimeStr, endTimeStr, now) {
    if (!startDateStr || !endDateStr) {
        return 'Please select both a start and an end date.';
    }
    if (new Date(startDateStr) > new Date(endDateStr)) {
        return 'Start date cannot be after end date.';
    }
    if (startDateStr === endDateStr && startTimeStr && endTimeStr && startTimeStr >= endTimeStr) {
        return 'Start time must be before end time on the same day.';
    }

    let selectedEndDateTime = new Date(endDateStr);
    const currentMoment = new Date(now); // Use passed 'now' for testability
    currentMoment.setSeconds(0,0);

    if (endTimeStr) {
        const [endHour, endMinute] = endTimeStr.split(':').map(Number);
        selectedEndDateTime.setHours(endHour, endMinute, 0, 0);
    } else {
        selectedEndDateTime.setHours(23, 59, 0, 0);
    }

    if (selectedEndDateTime > currentMoment) {
        return 'The selected end date and time cannot be later than the current moment.';
    }
    return null; // No error
}

describe('validateDateTimeSelection', () => {
    function validateDateTimeSelection(startDateStr, endDateStr, startTimeStr, endTimeStr, nowStr) {
        const now = new Date(nowStr); // Simulate 'now'
        now.setSeconds(0,0);

        if (!startDateStr || !endDateStr) return 'Please select both a start and an end date.';
        if (new Date(startDateStr) > new Date(endDateStr)) return 'Start date cannot be after end date.';
        if (startDateStr === endDateStr && startTimeStr && endTimeStr && startTimeStr >= endTimeStr) {
            return 'Start time must be before end time on the same day.';
        }
        let selectedEndDateTime = new Date(endDateStr);
        if (endTimeStr) {
            const [endHour, endMinute] = endTimeStr.split(':').map(Number);
            selectedEndDateTime.setHours(endHour, endMinute, 0, 0);
        } else {
            selectedEndDateTime.setHours(23, 59, 0, 0);
        }
        if (selectedEndDateTime > now) {
            return 'The selected end date and time cannot be later than the current moment.';
        }
        return null;
    }


    test('should return error if end date is in the future', () => {
        const now = '2025-05-13T10:00:00'; // Current time for test
        const result = validateDateTimeSelection('2025-05-13', '2025-05-14', '08:00', '17:00', now);
        expect(result).toBe('The selected end date and time cannot be later than the current moment.');
    });

    test('should return error if end time on current day is in the future', () => {
        const now = '2025-05-13T10:00:00';
        const result = validateDateTimeSelection('2025-05-13', '2025-05-13', '08:00', '12:00', now);
        expect(result).toBe('The selected end date and time cannot be later than the current moment.');
    });

    test('should return null for valid past date range', () => {
        const now = '2025-05-13T10:00:00';
        const result = validateDateTimeSelection('2025-05-12', '2025-05-12', '08:00', '17:00', now);
        expect(result).toBeNull();
    });

    test('should return null if end time on current day is in the past', () => {
        const now = '2025-05-13T10:00:00';
        const result = validateDateTimeSelection('2025-05-13', '2025-05-13', '08:00', '09:00', now);
        expect(result).toBeNull();
    });
    
    test('should return error if start date is after end date', () => {
        const now = '2025-05-13T10:00:00';
        const result = validateDateTimeSelection('2025-05-12', '2025-05-11', null, null, now);
        expect(result).toBe('Start date cannot be after end date.');
    });
});