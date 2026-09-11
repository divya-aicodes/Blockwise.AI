from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_application
from backend.app.routes.decisions import DecisionStore


@pytest.fixture()
def client(tmp_path: Path):
    with TestClient(create_application(maintenance_requests_path=tmp_path / "requirements.csv")) as client:
        yield client


def create_plan(client):
    requirement = client.post('/create-maintenance', json={
        'asset_id': 'AST-02-01', 'job_type': 'INSPECTION', 'urgency': 'HIGH',
        'minimum_duration_min': 60, 'earliest_start_time': '2026-09-09T06:00:00+05:30',
        'preferred_start_time': '2026-09-09T08:00:00+05:30', 'latest_end_time': '2026-09-09T22:00:00+05:30',
    })
    assert requirement.status_code == 201
    plans = client.post('/generate-alternatives', json={
        'maintenance_id': requirement.json()['maintenance_id'], 'top_n': 1,
        'solver_timeout_seconds': 10, 'max_train_delay_min': 360,
    })
    assert plans.status_code == 200
    return plans.json()['alternatives'][0]


def test_decision_validates_ids_and_decision_enum(client):
    assert client.post('/plan-decision', json={'plan_id':'P999','maintenance_id':'M999','decision':'APPROVED'}).status_code == 404
    assert client.post('/plan-decision', json={'plan_id':'P999','maintenance_id':'M999','decision':'EXECUTE'}).status_code == 422
    plan = create_plan(client)
    assert client.post('/plan-decision', json={'plan_id':plan['plan_id'],'maintenance_id':'M999','decision':'REJECTED'}).status_code == 422


def test_approval_revalidates_persists_and_is_idempotent(client):
    plan = create_plan(client)
    payload = {'plan_id':plan['plan_id'], 'maintenance_id':plan['maintenance_id'], 'decision':'APPROVED'}
    response = client.post('/plan-decision', json=payload)
    assert response.status_code == 200, response.text
    record = response.json()
    assert record['execution_started'] is False
    assert record['evidence']['simulation']['kpis']['maintenance_completed'] is True
    assert record['evidence']['simulation']['kpis']['conflicts_detected'] == 0
    assert record['evidence']['plan'] == plan
    assert client.post('/plan-decision',json=payload).json() == record
    reloaded = DecisionStore(client.app.state.decision_store.path)
    assert len(reloaded.records) == 1
    assert reloaded.records[0] == record
    rejected = client.post('/plan-decision',json={**payload,'decision':'REJECTED'}).json()
    assert rejected['decision_id'] != record['decision_id']
    assert len(DecisionStore(reloaded.path).records) == 2
    assert client.post('/plan-decision',json={**payload,'decision':'MODIFY'}).json()['decision'] == 'MODIFY'


def test_incomplete_simulation_cannot_be_approved(client):
    plan = create_plan(client)
    with patch('backend.app.routes.decisions.run_scenario', return_value={'kpis':{'conflicts_detected':0,'maintenance_completed':False}}):
        response = client.post('/plan-decision',json={'plan_id':plan['plan_id'],'maintenance_id':plan['maintenance_id'],'decision':'APPROVED'})
    assert response.status_code == 409
    assert client.app.state.decision_store.records == []


def test_failed_write_does_not_record_success(client):
    plan = create_plan(client)
    with patch('backend.app.routes.decisions.os.replace',side_effect=OSError('Disk unavailable')):
        response = client.post('/plan-decision',json={'plan_id':plan['plan_id'],'maintenance_id':plan['maintenance_id'],'decision':'REJECTED'})
    assert response.status_code == 503
    assert client.app.state.decision_store.records == []
