document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // --- DOM Elements ---
    const serialPortsSelect = document.getElementById('serialPorts');
    const baudRateSelect = document.getElementById('baudRate');
    const connectBtn = document.getElementById('connectBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const refreshPortsBtn = document.getElementById('refreshPortsBtn');
    const connectionStatus = document.getElementById('connectionStatus');
    const serialOutputDiv = document.getElementById('serialOutput');
    const clearOutputBtn = document.getElementById('clearOutputBtn');
    const autoscrollCheck = document.getElementById('autoscrollCheck');
    const serialInput = document.getElementById('serialInput');
    const sendBtn = document.getElementById('sendBtn');
    const newlineSelect = document.getElementById('newlineSelect');
    const errorAlertContainer = document.getElementById('errorAlertContainer');
    const plotCanvas = document.getElementById('livePlot');
    const clearPlotBtn = document.getElementById('clearPlotBtn');
    const plotPointCountSpan = document.getElementById('plotPointCount');
    const plotMaxPointsSpan = document.getElementById('plotMaxPoints');

    // --- State ---
    let connected = false;
    const MAX_PLOT_POINTS = 100;
    plotMaxPointsSpan.textContent = MAX_PLOT_POINTS;
    let plotData = {
        labels: [],
        datasets: [{
            label: 'Serial Data',
            data: [],
            borderColor: 'rgb(75, 192, 192)',
            borderWidth: 1.5,
            tension: 0.1,
            fill: false,
            pointRadius: 1,
            pointHoverRadius: 3
        }]
    };
    let errorToastCounter = 0;

    // --- Chart.js Setup ---
    const ctx = plotCanvas.getContext('2d');
    const liveChart = new Chart(ctx, {
        type: 'line',
        data: plotData,
        options: {
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    ticks: { display: false },
                    grid: { display: false }
                },
                y: {
                    beginAtZero: false,
                    ticks: { font: { size: 10 } }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: true, mode: 'index', intersect: false }
            },
            animation: { duration: 0 },
            maintainAspectRatio: false,
            responsive: true
        }
    });

    // --- Helper Functions ---
    function updateConnectionStatus(isConnected, port = null) {
        connected = isConnected;
        connectBtn.disabled = isConnected;
        disconnectBtn.disabled = !isConnected;
        sendBtn.disabled = !isConnected;
        serialPortsSelect.disabled = isConnected;
        baudRateSelect.disabled = isConnected;
        refreshPortsBtn.disabled = isConnected;
        serialInput.disabled = !isConnected;
        newlineSelect.disabled = !isConnected;

        connectionStatus.textContent = isConnected ? `Connected (${port})` : 'Disconnected';
        connectionStatus.classList.toggle('bg-success', isConnected);
        connectionStatus.classList.toggle('bg-secondary', !isConnected);
        connectionStatus.classList.remove('bg-danger');
    }

    function addSerialLog(message, type = 'received') {
        const timestamp = new Date().toLocaleTimeString();
        const lineDiv = document.createElement('div');
        lineDiv.innerHTML = `<span class="text-muted small me-2">[${timestamp}]</span>`;

        const messageSpan = document.createElement('span');
        messageSpan.textContent = message;

        if (type === 'sent') {
            messageSpan.style.color = 'blue';
            messageSpan.innerHTML = `&rarr; ${message}`;
        } else if (type === 'error') {
            messageSpan.style.color = 'red';
            messageSpan.style.fontWeight = 'bold';
            messageSpan.textContent = `ERROR: ${message}`;
        } else if (type === 'info') {
            messageSpan.style.color = 'green';
            messageSpan.style.fontStyle = 'italic';
        }
        lineDiv.appendChild(messageSpan);
        serialOutputDiv.appendChild(lineDiv);

        // Autoscroll
        if (autoscrollCheck.checked) {
            const threshold = 50;
            const isScrolledToBottom = serialOutputDiv.scrollHeight - serialOutputDiv.clientHeight <= serialOutputDiv.scrollTop + threshold;
            if (isScrolledToBottom) {
                serialOutputDiv.scrollTop = serialOutputDiv.scrollHeight;
            }
        }
    }

    function showErrorToast(message) {
        errorToastCounter++;
        const toastId = `errorToast-${errorToastCounter}`;
        const toastHTML = `
            <div id="${toastId}" class="toast align-items-center text-white bg-danger border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        errorAlertContainer.insertAdjacentHTML('beforeend', toastHTML);
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
        toast.show();
        toastElement.addEventListener('hidden.bs.toast', () => toastElement.remove());

        console.error("Error:", message);
        addSerialLog(message, 'error');
        connectionStatus.classList.remove('bg-success', 'bg-secondary');
        connectionStatus.classList.add('bg-danger');
        connectionStatus.textContent = 'Error';
    }

    function updatePlot(value) {
        // Use a running index for x-axis
        const nextIndex = plotData.labels.length > 0 ? plotData.labels[plotData.labels.length - 1] + 1 : 1;
        plotData.labels.push(nextIndex);
        plotData.datasets[0].data.push(value);
        while (plotData.labels.length > MAX_PLOT_POINTS) {
            plotData.labels.shift();
            plotData.datasets[0].data.shift();
        }
        plotPointCountSpan.textContent = plotData.labels.length;
        liveChart.update();
    }

    function clearPlot() {
        plotData.labels = [];
        plotData.datasets[0].data = [];
        plotPointCountSpan.textContent = 0;
        liveChart.update();
    }

    function getSelectedNewline() {
        switch (newlineSelect.value) {
            case 'lf': return '\n';
            case 'cr': return '\r';
            case 'crlf': return '\r\n';
            default: return '';
        }
    }

    // --- Event Listeners ---
    refreshPortsBtn.addEventListener('click', () => {
        socket.emit('get_ports');
    });

    connectBtn.addEventListener('click', () => {
        const selectedPort = serialPortsSelect.value;
        const selectedBaudRate = baudRateSelect.value;
        if (selectedPort) {
            socket.emit('open_port', { port: selectedPort, baudrate: selectedBaudRate });
            serialOutputDiv.innerHTML = '';
            clearPlot();
            addSerialLog(`Attempting to connect to ${selectedPort}...`, 'info');
        } else {
            showErrorToast("Please select a serial port.");
        }
    });

    disconnectBtn.addEventListener('click', () => {
        socket.emit('close_port');
        addSerialLog('Disconnecting...', 'info');
    });

    sendBtn.addEventListener('click', () => {
        const dataToSend = serialInput.value;
        if (dataToSend || dataToSend === "") {
            const newline = getSelectedNewline();
            socket.emit('send_data', { data: dataToSend, add_newline: newline });
        }
    });

    serialInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !sendBtn.disabled) {
            sendBtn.click();
        }
    });

    clearOutputBtn.addEventListener('click', () => {
        serialOutputDiv.innerHTML = '';
    });

    clearPlotBtn.addEventListener('click', () => {
        clearPlot();
    });

    // --- SocketIO Event Handlers ---
    socket.on('connect', () => {
        socket.emit('get_ports');
        if (connectionStatus.classList.contains('bg-danger')) {
            updateConnectionStatus(false);
        }
        addSerialLog('Connected to server.', 'info');
        // Demo: Uncomment to see live plot demo
        // setInterval(() => socket.emit('plot_data', { value: Math.random() * 100 }), 1000);
    });

    socket.on('disconnect', (reason) => {
        addSerialLog(reason === 'io server disconnect' ? 'Disconnected by server.' : 'Disconnected from server. Check connection.', reason === 'io server disconnect' ? 'error' : 'error');
        updateConnectionStatus(false);
    });

    socket.on('connect_error', (err) => {
        showErrorToast(`Server connection failed: ${err.message}`);
        updateConnectionStatus(false);
    });

    socket.on('serial_ports', (data) => {
        let previousPort = localStorage.getItem('selectedSerialPort');
        const currentSelection = serialPortsSelect.value || previousPort;
        serialPortsSelect.innerHTML = '';
        if (data.ports && data.ports.length > 0) {
            data.ports.forEach(port => {
                const option = document.createElement('option');
                option.value = port.device;
                let description = port.description || 'Serial Port';
                if (description.includes('(')) {
                    description = description.substring(0, description.indexOf('(')).trim();
                }
                option.textContent = `${port.device} (${description})`;
                serialPortsSelect.appendChild(option);
            });
            if ([...serialPortsSelect.options].some(opt => opt.value === currentSelection)) {
                serialPortsSelect.value = currentSelection;
            }
            connectBtn.disabled = connected;
        } else {
            const option = document.createElement('option');
            option.textContent = 'No ports found';
            option.disabled = true;
            serialPortsSelect.appendChild(option);
            connectBtn.disabled = true;
        }
    });

    socket.on('status', (data) => {
        updateConnectionStatus(data.connected, data.port);
        if (data.connected) {
            if (data.port) {
                localStorage.setItem('selectedSerialPort', data.port);
                serialPortsSelect.value = data.port;
            }
            addSerialLog(`Successfully connected to ${data.port}`, 'info');
            serialInput.focus();
        } else {
            localStorage.removeItem('selectedSerialPort');
            if (!disconnectBtn.disabled) {
                addSerialLog('Disconnected.', 'info');
            }
        }
    });

    socket.on('serial_data', (data) => {
        addSerialLog(data.data, data.type || 'received');
        if (data.type === 'sent') {
            serialInput.value = '';
        }
    });

    socket.on('plot_data', (data) => {
        if (typeof data.value === 'number') {
            updatePlot(data.value);
        } else {
            console.warn('Received non-numeric plot data:', data.value);
        }
    });

    socket.on('error', (data) => {
        showErrorToast(data.message);
    });

    // Initial port fetch
    socket.emit('get_ports');

    // --- Example usage for live plot (for demo/testing) ---
    // To see a demo, open the browser console and run:
    // setInterval(() => socket.emit('plot_data', { value: Math.random() * 100 }), 1000);
});