# CennSerial Monitor

A web-based serial port monitor and live plotter built with Flask, Flask-SocketIO, pyserial, Bootstrap, and Chart.js.

## Features

- List available serial ports on your system
- Connect/disconnect to serial ports with selectable baud rate
- View serial output in real time
- Send data to the serial port (with configurable newline)
- Live plot of numeric serial data (auto-detects numbers)
- Multi-client support (multiple browser tabs can view the same port)
- Responsive UI with Bootstrap 5
- Error handling and toast notifications

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the server

```bash
python app.py
```

The server will start at [http://localhost:5000](http://localhost:5000).

### 3. Open the web interface

Visit [http://localhost:5000](http://localhost:5000) in your browser.

## Usage

- Select a serial port and baud rate, then click **Connect**.
- View incoming serial data in the "Serial Output" tab.
- Send data using the input box at the bottom.
- Switch to the "Live Plot" tab to see numeric data plotted in real time.
- Use the **Clear Output** and **Clear Plot** buttons as needed.
- To see a live plot demo without hardware, open your browser console and run:
  ```js
  setInterval(() => socket.emit('plot_data', { value: Math.random() * 100 }), 500);
  ```

## Troubleshooting

- **No serial ports listed?**
  - Make sure your user has permission to access serial devices (e.g., add to `dialout` group on Linux).
  - Try running: `python3 -m serial.tools.list_ports`
  - Plug in a USB serial device and refresh the page.

- **Can't connect to port?**
  - Make sure no other program is using the port.
  - Check permissions.

- **Live plot not updating?**
  - Only numeric lines are plotted. Ensure your device sends numbers.

## Project Structure

```
app.py                  # Flask + SocketIO backend
requirements.txt        # Python dependencies
/static/
    css/style.css       # Custom styles
    js/main.js          # Frontend logic (Socket.IO, Chart.js, UI)
/templates/
    index.html          # Main HTML page
/tests/                 # Pytest-based backend tests
```

## License

MIT License

---

**Made with Flask, Socket.IO, Bootstrap, and Chart.js**
