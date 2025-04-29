# tests/test_app.py

import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def patch_serial_and_eventlet(monkeypatch):
    # Patch serial.Serial and serial.SerialException in app namespace
    def serial_constructor(*a, **kw):
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial_instance.in_waiting = 0
        mock_serial_instance.port = a[0] if a else '/dev/ttyACM0'
        mock_serial_instance.readline.return_value = b''
        mock_serial_instance.write.return_value = None
        mock_serial_instance.close.return_value = None
        return mock_serial_instance
    monkeypatch.setattr('app.serial.Serial', serial_constructor)
    monkeypatch.setattr('app.serial.SerialException', Exception)
    # Patch comports
    mock_comports = MagicMock(return_value=[
        MagicMock(device='/dev/ttyACM0', description='USB Serial Device'),
        MagicMock(device='/dev/ttyS0', description='ttyS0 Serial Port')
    ])
    monkeypatch.setattr('app.serial.tools.list_ports.comports', mock_comports)
    # Patch eventlet.spawn and sleep
    monkeypatch.setattr('app.eventlet.spawn', lambda target, *args, **kwargs: None)  # Prevents test hang
    monkeypatch.setattr('app.eventlet.sleep', lambda x: None)
    # Do NOT set app.serial_connection here
    return mock_serial_instance

from app import app, socketio

@pytest.fixture
def client():
    app.config['TESTING'] = True
    flask_client = app.test_client()
    socketio_client = socketio.test_client(app, flask_test_client=flask_client)
    # Reset serial_connection before each test
    import app as app_module
    app_module.serial_connection = None
    yield socketio_client
    if socketio_client.is_connected():
        socketio_client.disconnect()

def test_index_route(client):
    response = client.flask_test_client.get('/')
    assert response.status_code == 200
    assert b'<title>Web Serial Monitor</title>' in response.data

def test_socketio_connect_and_initial_state(client):
    assert client.is_connected()
    received = client.get_received()
    ports_event = next((e for e in received if e['name'] == 'serial_ports'), None)
    assert ports_event is not None
    assert 'ports' in ports_event['args'][0]
    assert len(ports_event['args'][0]['ports']) == 2
    status_event = next((e for e in received if e['name'] == 'status'), None)
    assert status_event is not None
    assert status_event['args'][0]['connected'] is False

def test_get_ports_event(client):
    client.emit('get_ports')
    received = client.get_received()
    ports_event = next((e for e in received if e['name'] == 'serial_ports'), None)
    assert ports_event is not None
    assert len(ports_event['args'][0]['ports']) == 2

def test_open_port_success(client, patch_serial_and_eventlet):
    patch_serial_and_eventlet.is_open = False  # Simulate port is closed before open
    patch_serial_and_eventlet.port = '/dev/ttyACM0'
    client.emit('open_port', {'port': '/dev/ttyACM0', 'baudrate': 115200})
    patch_serial_and_eventlet.is_open = True  # Simulate port is now open after open_port
    received = client.get_received()
    status_event = next((e for e in received if e['name'] == 'status'), None)
    assert status_event is not None
    assert status_event['args'][0]['connected'] is True
    assert status_event['args'][0]['port'] == '/dev/ttyACM0'

def test_close_port(client, patch_serial_and_eventlet):
    patch_serial_and_eventlet.is_open = False
    patch_serial_and_eventlet.port = '/dev/ttyACM0'
    client.emit('open_port', {'port': '/dev/ttyACM0', 'baudrate': 115200})
    patch_serial_and_eventlet.is_open = True  # Simulate port is now open
    client.get_received()
    # Now close the port
    patch_serial_and_eventlet.is_open = False  # Simulate port is now closed
    client.emit('close_port')
    received = client.get_received()
    status_event = next((e for e in received if e['name'] == 'status'), None)
    assert status_event is not None
    assert status_event['args'][0]['connected'] is False

def test_send_data_success(client, patch_serial_and_eventlet):
    patch_serial_and_eventlet.is_open = True
    patch_serial_and_eventlet.port = '/dev/ttyACM0'
    client.emit('open_port', {'port': '/dev/ttyACM0', 'baudrate': 115200})
    client.get_received()
    client.emit('send_data', {'data': 'Hello', 'add_newline': '\n'})
    received = client.get_received()
    echo_event = next((e for e in received if e['name'] == 'serial_data'), None)
    assert echo_event is not None
    assert echo_event['args'][0]['data'].startswith('->')

def test_send_data_not_connected(client, patch_serial_and_eventlet):
    patch_serial_and_eventlet.is_open = False
    import app as app_module
    app_module.serial_connection = None  # Ensure global is None
    client.emit('send_data', {'data': 'test', 'add_newline': '\n'})
    received = client.get_received()
    error_event = next((e for e in received if e['name'] == 'error'), None)
    assert error_event is not None
    assert 'Serial port not connected' in error_event['args'][0]['message']
