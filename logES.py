from flask import request
from elasticsearch import Elasticsearch
from datetime import datetime
import time
from celery import Celery
from elasticsearch.exceptions import ElasticsearchException

es_client = Elasticsearch(['http://localhost:9200'])
celery = Celery(__name__, broker='redis://localhost:6379/0')

class ElasticLogger:
    @celery.task
    def process_log(user_id, opid, log_type, log_level, error, message):
        index_name = f"medbud-logger-{user_id}-{int(time.time())}"

        log_data = {
            'user_id': user_id,
            'opid': opid,
            'log_type': log_type,
            'log_level': log_level,
            'error': error,
            'message': message,
            'timestamp': datetime.now()
        }

        try:
            es_client.index(index=index_name, doc_type='_doc', body=log_data)
        except ElasticsearchException as e:
            print(f"Failed to insert log data into Elasticsearch: {str(e)}")
