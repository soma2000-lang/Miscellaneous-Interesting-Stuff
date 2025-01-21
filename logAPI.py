from flask import request
import threading
import time
from queue import Queue

class LogAPI:
    @staticmethod
     def _validate_data(self, data):
        user_id = data.get('user_id')
        opid = data.get('opid')
        log_type = data.get('log_type')
        log_level = data.get('log_level')
        error = data.get('error')
        message = data.get('message')

        if any(field is None for field in [user_id, opid, log_type, log_level, message]):
            return "One or more required fields are missing."
        
        log_level = log_level.lower()

        allowed_log_levels = ['info', 'warning', 'error', 'verbose', 'severe']
        if log_level not in allowed_log_levels:
            return "Invalid log_level. Allowed values: info, warning, error, verbose, severe"

        if error is None:
            error = ''

        return None

    @staticmethod
    def post(self):
        response_thread = threading.Thread(target=self.send_response)
        response_thread.start()

        _data = request.json

        validation_result = self._validate_data(data)
        if validation_result is not None:
            user_id = _data.get('user_id')
            opid = _data.get('opid')
            error = _data.get('error')
            reason = f"Validation of data failed: {validation_result}"
            Queue.queueElasticLogger(user_id, opid, "ES_LOGGER", "warning", null, reason)

        user_id = _data.get('user_id')
        opid = _data.get('opid')
        log_type = _data.get('log_type')
        log_level = _data.get('log_level')
        error = _data.get('error')
        message = _data.get('message')

        Queue.queueElasticLogger(user_id, opid, log_type, log_level, error, message)

    def send_response(self):
        time.sleep(0.1)
        response = jsonify("Data recevied sent for logging.")
        response.status_code = 200
        return response
