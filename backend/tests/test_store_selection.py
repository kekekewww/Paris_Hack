import pytest


@pytest.fixture
def main_module(monkeypatch, tmp_path):
    monkeypatch.setenv('CASE_DB_PATH', str(tmp_path / 'local-cases.sqlite3'))
    monkeypatch.delenv('CASE_STORE_URL', raising=False)
    monkeypatch.delenv('CASE_STORE_TOKEN', raising=False)
    from backend.app import main
    return main


def test_remote_configuration_selects_remote_without_creating_sqlite(main_module, monkeypatch, tmp_path):
    from backend.app import remote_store
    selected = object()
    monkeypatch.setenv('CASE_STORE_URL', 'https://demo.example.workers.dev/__internal/cases')
    monkeypatch.setenv('CASE_STORE_TOKEN', 'synthetic-storage-token')
    monkeypatch.setattr(remote_store.HTTPCaseStore, 'from_environment', classmethod(lambda cls: selected))
    app = main_module.create_app()
    assert app.state.store is selected


@pytest.mark.parametrize('name,value', [('CASE_STORE_URL', 'https://demo.example.workers.dev/__internal/cases'), ('CASE_STORE_TOKEN', 'synthetic-storage-token')])
def test_partial_remote_configuration_does_not_silently_fall_back_to_sqlite(main_module, monkeypatch, name, value):
    from backend.app.errors import ApiError
    monkeypatch.setenv(name, value)
    with pytest.raises(ApiError) as caught:
        main_module.create_app()
    assert caught.value.code == 'INVALID_CASE_STORE_CONFIG'


def test_default_storage_keeps_existing_sqlite(main_module):
    from backend.app.store import CaseStore
    assert isinstance(main_module.create_app().state.store, CaseStore)


@pytest.mark.parametrize('claim_type', ['inpatient', 'outpatient', 'critical_illness'])
def test_real_application_case_contract_round_trips_remote_store(main_module, monkeypatch, claim_type):
    import copy
    import json
    import httpx
    from fastapi.testclient import TestClient
    from backend.app.remote_store import HTTPCaseStore
    records = {}

    def command(request):
        body = json.loads(request.content)
        op = body['op']
        if op == 'cleanup':
            return httpx.Response(200, json={'result': 0})
        key = (body['owner_hash'], body.get('id') or body['case']['id'])
        if op in {'create', 'save'}:
            records[key] = copy.deepcopy(body['case'])
            result = records[key]
        elif op == 'get':
            result = records.get(key)
        else:
            result = records.pop(key, None) is not None
        return httpx.Response(200, json={'result': result})

    store = HTTPCaseStore('https://demo.example.workers.dev/__internal/cases', 'synthetic-storage-token', transport=httpx.MockTransport(command))
    monkeypatch.setenv('CASE_STORE_URL', 'https://demo.example.workers.dev/__internal/cases')
    monkeypatch.setenv('CASE_STORE_TOKEN', 'synthetic-storage-token')
    monkeypatch.setattr(HTTPCaseStore, 'from_environment', classmethod(lambda cls: store))
    with TestClient(main_module.create_app()) as client:
        response = client.post('/api/v1/cases', json={'entry_path': 'direct', 'claim_type_id': claim_type})
        assert response.status_code == 201
        item = response.json()
        path = '/api/v1/cases/' + item['id']
        assert client.get(path).json() == item
        for value in ('yes', 'no', 'unknown'):
            changed = client.patch(path, json={'conditions': {'insurer_requested_medical_authorization': value}})
            assert changed.status_code == 200
            assert changed.json()['conditions']['insurer_requested_medical_authorization'] == value
            assert client.get(path).json() == changed.json()
        assert client.delete(path).status_code == 200
        assert client.get(path).status_code == 404
