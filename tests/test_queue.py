from unittest.mock import patch, MagicMock
import random
from pathlib import Path
import openreview
import sys
import json
import pytest
import os
import time
import numpy as np
import shutil
import expertise.service
from expertise.dataset import ArchivesDataset, SubmissionsDataset
from expertise.models import elmo

@pytest.fixture
def create_elmo():
    def simple_elmo(config):
        archives_dataset = ArchivesDataset(archives_path=Path('tests/data/archives'))
        submissions_dataset = SubmissionsDataset(submissions_path=Path('tests/data/submissions'))

        elmoModel = elmo.Model(
            use_title=config['model_params'].get('use_title'),
            use_abstract=config['model_params'].get('use_abstract'),
            use_cuda=config['model_params'].get('use_cuda'),
            batch_size=config['model_params'].get('batch_size'),
            knn=config['model_params'].get('knn'),
            sparse_value=config['model_params'].get('sparse_value')
        )
        elmoModel.set_archives_dataset(archives_dataset)
        elmoModel.set_submissions_dataset(submissions_dataset)
        return elmoModel
    return simple_elmo

@pytest.fixture()
def openreview_context():
    """
    A pytest fixture for setting up a clean expertise-api test instance:
    `scope` argument is set to 'function', so each function will get a clean test instance.
    """
    config = {
        "LOG_FILE": "pytest.log",
        "OPENREVIEW_USERNAME": "openreview.net",
        "OPENREVIEW_PASSWORD": "1234",
        "OPENREVIEW_BASEURL": "http://localhost:3000",
        "SUPERUSER_FIRSTNAME": "Super",
        "SUPERUSER_LASTNAME": "User",
        "SUPERUSER_TILDE_ID": "~Super_User1",
        "SUPERUSER_EMAIL": "info@openreview.net",
        "SPECTER_DIR": '../expertise-utils/specter/',
        "MFR_VOCAB_DIR": '../expertise-utils/multifacet_recommender/feature_vocab_file',
        "MFR_CHECKPOINT_DIR": '../expertise-utils/multifacet_recommender/mfr_model_checkpoint/',
        "WORKING_DIR": 'tmp',
        "TEST_NUM": random.randint(1, 100000)
    }
    app = expertise.service.create_app(
        config=config
    )

    with app.app_context():
        yield {
            "app": app,
            "test_client": app.test_client(),
            "config": config
        }

@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_url": "redis://localhost:6379/10",
        "result_backend": "redis://localhost:6379/10",
        "task_track_started": True,
        "task_serializer": "pickle",
        "result_serializer": "pickle",
        "accept_content": ["pickle", "application/x-python-serialize"],
        "task_create_missing_queues": True,
    }

@pytest.fixture(scope="session")
def celery_includes():
    return ["expertise.service.celery_tasks"]

@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {
        "queues": ("userpaper", "expertise"),
        "perform_ping_check": False,
        "concurrency": 4,
    }

def test_elmo_queue(openreview_context, celery_app, celery_worker):
    test_client = openreview_context['test_client']
    server_config = openreview_context['config']
    test_num = server_config['TEST_NUM']
    
    if os.path.isdir(f'~{test_num}'):
        shutil.rmtree(f'~{test_num}')

    # Gather config
    config = {
        'name': 'test_run',
        'match_group': ["ABC.cc"],
        "model": "elmo",
        "model_params": {
            "use_title": False,
            "use_abstract": True,
            "average_score": True,
            "max_score": False
        }
    }
    # Filesystem setup - Parse csv_submissions into list of csv strings
    response = test_client.post(
        '/expertise',
        data = json.dumps({'TEST_NUM': test_num, **config}),
        content_type='application/json'
    )
    assert response.status_code == 500, f'{response.json}' # Missing a required field

    config.update({'paper_invitation': 'ABC.cc/-/Submission'})
    response = test_client.post(
        '/expertise',
        data = json.dumps({'TEST_NUM': test_num, **config}),
        content_type='application/json'
    )
    assert response.status_code == 200, f'{response.json}'
    job_id = response.json['job_id']
    # Query until job is complete
    time.sleep(5)
    response = test_client.get('/results', query_string={'TEST_NUM': test_num, 'job_id': job_id})
    assert response.status_code == 500

    response = test_client.get('/jobs', query_string={'TEST_NUM': test_num}).json['results']
    assert len(response) == 1
    while response[0]['status'] == 'Processing':
        time.sleep(5)
        response = test_client.get('/jobs', query_string={'TEST_NUM': test_num}).json['results']
    
    assert response[0]['status'] == 'Completed'

    # Check for results
    assert os.path.isdir(f"{server_config['WORKING_DIR']}/~{test_num}/{job_id}")
    assert os.path.isfile(f"{server_config['WORKING_DIR']}/~{test_num}/{job_id}/test_run.csv")

    response = test_client.get('/results', query_string={'TEST_NUM': test_num, 'job_id': job_id})
    metadata = response.json['metadata']
    assert metadata['submission_count'] == 2
    response = response.json['results']
    for item in response:
        submission_id, profile_id, score = item['submission'], item['user'], float(item['score'])
        assert len(submission_id) >= 1
        assert len(profile_id) >= 1
        assert profile_id.startswith('~')
        assert score >= 0 and score <= 1
        
    response = test_client.get('/results', query_string={'TEST_NUM': test_num, 'job_id': job_id, 'delete_on_get': True}).json['results']
    assert not os.path.isdir(f"{server_config['WORKING_DIR']}/~{test_num}/{job_id}")
    assert not os.path.isfile(f"{server_config['WORKING_DIR']}/~{test_num}/{job_id}/test_run.csv")

    # Gather second config with an error in the model field
    config = {
        'name': 'test_run',
        'paper_invitation': 'ABC.cc/-/Submission',
        'match_group': ["ABC.cc"],
        'csv_submissions': 'csv_submissions.csv',
        "model": "elmo",
        "model_params": {
            "use_title": None,
            "use_abstract": None,
            "average_score": None,
            "max_score": None
        }
    }
    response = test_client.post(
        '/expertise',
        data = json.dumps({'TEST_NUM': test_num, **config}),
        content_type='application/json'
    )
    assert response.status_code == 200, f'{response.json}'
    job_id = response.json['job_id']

    # Query until job is complete
    time.sleep(5)
    response = test_client.get('/results', query_string={'TEST_NUM': test_num, 'job_id': job_id})
    assert response.status_code == 500

    response = test_client.get('/jobs', query_string={'TEST_NUM': test_num}).json['results']
    assert len(response) == 1
    while response[0]['status'] == 'Processing':
        time.sleep(5)
        response = test_client.get('/jobs', query_string={'TEST_NUM': test_num}).json['results']
    
    assert response[0]['status'] == 'Error'
    assert os.path.isfile(f"{server_config['WORKING_DIR']}/~{test_num}/err.log")

    # Clean up test
    shutil.rmtree(f"{server_config['WORKING_DIR']}/")
    os.remove('pytest.log')
    os.remove('default.log')