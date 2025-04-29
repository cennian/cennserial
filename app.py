import eventlet
eventlet.monkey_patch()

import logging
import serial
import serial.tools.list_ports
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'  # Change for production
socketio = SocketIO(app, async_mode='eventlet')

# --- Globals ---
serial_thread = None
serial_connection = None
stop_thread_flag = threading.Event()
serial_lock = threading.Lock()

# --- Serial Port Helpers ---
def list_serial_ports():
    ports = list(serial.tools.list_ports.comports())
    logging.info(f"Raw comports: {ports}")
    port_list = []
    for p in ports:
        logging.info(f"Port object: device={getattr(p, 'device', None)}, description={getattr(p, 'description', None)}, hwid={getattr(p, 'hwid', None)}, name={getattr(p, 'name', None)}, vid={getattr(p, 'vid', None)}, pid={getattr(p, 'pid', None)}")
        port_list.append({'device': p.device, 'description': p.description})
    logging.info(f"Serial ports (parsed): {port_list}")
    # Explicitly check for /dev/ttyACM0
    if not any(p['device'] == '/dev/ttyACM0' for p in port_list):
        logging.warning("/dev/ttyACM0 not found in port_list!")
    if not port_list:
        logging.warning("No serial ports found. Is a device connected? Check permissions (dialout group on Linux).")
    return port_list

def read_from_serial(ser):
    logging.info(f"Serial read thread started for {ser.port}")
    while not stop_thread_flag.is_set() and ser and ser.is_open:
        try:
            if ser.in_waiting > 0:
                raw = ser.readline()
                line = raw.decode('utf-8', errors='replace').strip()
                if line:
                    logging.info(f"Received: {line}")
                    socketio.emit('serial_data', {'data': line})
                    try:
                        val = float(line)
                        socketio.emit('plot_data', {'value': val})
                    except ValueError:
                        pass
            eventlet.sleep(0.01)
        except serial.SerialException as e:
            logging.error(f"Serial read error: {e}")
            socketio.emit('error', {'message': f"Serial read error: {e}"})
            socketio.start_background_task(close_serial_port)
            break
        except Exception as e:
            logging.error(f"Unexpected serial read error: {e}")
            socketio.emit('error', {'message': f"Unexpected error: {e}"})
            socketio.start_background_task(close_serial_port)
            break
    logging.info(f"Serial read thread for {ser.port} stopped.")

def close_serial_port():
    global serial_connection, serial_thread
    with serial_lock:
        if not stop_thread_flag.is_set():
            stop_thread_flag.set()
        t = serial_thread
        c = serial_connection
        serial_thread = None
        serial_connection = None
        if t and hasattr(t, "is_alive") and t.is_alive():
            t.join(timeout=1.0)
        if c and getattr(c, "is_open", False):
            try:
                c.close()
                logging.info(f"Closed serial port {c.port}")
            except Exception as e:
                logging.error(f"Error closing port: {e}")
        # Remove broadcast=True, just use socketio.emit
        socketio.emit('status', {'connected': False, 'port': None})
        stop_thread_flag.clear()

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ports')
def ports_api():
    # Quick test endpoint: visit http://localhost:5000/ports to see detected ports
    return {'ports': list_serial_ports()}

@app.route('/test_backend')
def test_backend():
    # Test HTTP endpoint to check backend is running
    logging.info("HTTP /test_backend called")
    return {'status': 'ok', 'message': 'Backend is running and HTTP route works.'}

# --- SocketIO Events ---
@socketio.on('connect')
def on_connect():
    emit('serial_ports', {'ports': list_serial_ports()})
    if serial_connection and getattr(serial_connection, "is_open", False):
        emit('status', {'connected': True, 'port': serial_connection.port})
    else:
        emit('status', {'connected': False, 'port': None})

@socketio.on('get_ports')
def on_get_ports():
    emit('serial_ports', {'ports': list_serial_ports()})

@socketio.on('open_port')
def on_open_port(data):
    global serial_connection, serial_thread
    port = data.get('port')
    baudrate = int(data.get('baudrate', 9600))
    if not port:
        emit('error', {'message': 'No port specified.'})
        return
    with serial_lock:
        if serial_connection and getattr(serial_connection, "is_open", False):
            if serial_connection.port == port:
                emit('status', {'connected': True, 'port': port})
                return
            else:
                emit('error', {'message': f"Another port ({serial_connection.port}) is open. Disconnect first."})
                return
        try:
            if serial_thread and hasattr(serial_thread, "is_alive") and serial_thread.is_alive():
                close_serial_port()
            ser = serial.Serial(port, baudrate, timeout=1)
            if ser.is_open:
                serial_connection = ser
                stop_thread_flag.clear()
                serial_thread = eventlet.spawn(read_from_serial, serial_connection)
                # Remove broadcast=True, just use socketio.emit
                socketio.emit('status', {'connected': True, 'port': port})
            else:
                emit('error', {'message': f"Failed to open {port}."})
        except Exception as e:
            logging.error(f"Failed to open port {port}: {e}")
            emit('error', {'message': f"Failed to open {port}: {e}"})

@socketio.on('close_port')
def on_close_port():
    socketio.start_background_task(close_serial_port)

@socketio.on('send_data')
def on_send_data(data):
    msg = data.get('data')
    add_newline = data.get('add_newline', True)
    if serial_connection and getattr(serial_connection, "is_open", False):
        if msg is not None:
            try:
                payload = msg
                if isinstance(add_newline, str):
                    payload += add_newline
                elif add_newline is True:
                    payload += '\r\n'
                serial_connection.write(payload.encode('utf-8', errors='replace'))
                logging.info(f"Sent: {payload.strip()}")
                emit('serial_data', {'data': f"-> {msg}", 'type': 'sent'})
            except Exception as e:
                logging.error(f"Serial write error: {e}")
                emit('error', {'message': f"Serial write error: {e}"})
                socketio.start_background_task(close_serial_port)
    else:
        emit('error', {'message': 'Serial port not connected.'})

@socketio.on('test_event')
def handle_test_event(data):
    logging.info(f"Received test_event from client: {data}")
    emit('test_response', {'status': 'ok', 'echo': data})

# --- Main ---
if __name__ == '__main__':
    logging.info("Starting server at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, use_reloader=True, debug=True)
