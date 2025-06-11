// Cherum Drone Control Interface - Main Application
//
const FLIGHT_MODE_TO_COMMAND = {
  "RETURN_TO_LAUNCH": "rtl",
  "HOLD": "loiter",
  "LAND": "land"
}

class DroneControl {
  constructor() {
    this.connectionStatus = {
      connected: false,
      lastConnection: 'Never',
      checkInterval: null
    };

    this.telemetry = {
      position: { latitude: null, longitude: null, altitude: null },
      battery: { percentage: null, id: null },
      flightMode: null,
      armed: false,
      inAir: false
    };

    this.loading = { telemetry: true, connection: true };
    this.error = null;

    // Map related properties
    this.map = null;
    this.droneMarker = null;
    this.trajectory = null;
    this.trajectoryPoints = [];
    this.maxTrajectoryPoints = 1000; // Limit trajectory points to prevent memory issues

    this.init();
  }

  init() {
    // Get DOM elements
    this.elements = {
      status: document.getElementById('status'),
      lastConnection: document.getElementById('last-connection'),
      longitude: document.getElementById('longitude'),
      latitude: document.getElementById('latitude'),
      altitude: document.getElementById('altitude'),
      battery: document.getElementById('battery'),
      batteryIcon: document.getElementById('battery-icon'),
      flightMode: document.getElementById('flight-mode'),
      armedStatus: document.getElementById('armed-status'),
      airStatus: document.getElementById('air-status'),
      themeToggle: document.getElementById('theme-toggle'),
      errorContainer: document.getElementById('error-container'),
      commandButtons: document.getElementsByName("command")
    };

    // Initialize map
    this.initMap();

    this.initListeners();

    // Start data fetching
    this.updateConnectionStatus();
    this.updateTelemetry();

    // Set up intervals
    this.connectionInterval = setInterval(() => this.updateConnectionStatus(), 1000);
    this.telemetryInterval = setInterval(() => this.updateTelemetry(), 500);
  }

  initListeners() {
    for (const button of this.elements.commandButtons) {
      button.addEventListener("click", async (e) => {
        e.preventDefault()
        await this.sendCommand(e.target.value)
        e.target.classList.add("primary")
        e.target.classList.remove("secondary")
      });
    }
  }

  async sendCommand(command) {
    const form = new FormData();
    form.append("command", command)
    return fetch("/command", {
      method: "POST",
      body: form
    })
  }

  async updateConnectionStatus() {
    try {
      const response = await fetch('/last/connection');
      const text = await response.text();

      if (text && text !== 'Never') {
        const date = new Date(text.replace(' ', 'T'));
        const now = new Date();
        this.connectionStatus.connected = (now - date) < 10000;
        this.connectionStatus.lastConnection = this.formatDateTime(date);
      } else {
        this.connectionStatus.connected = false;
        this.connectionStatus.lastConnection = 'Never';
      }

      this.updateConnectionUI();
      this.loading.connection = false;
    } catch (error) {
      console.error('Error fetching connection status:', error);
      this.connectionStatus.connected = false;
      this.showError('Error al obtener el estado de conexión');
    }
  }

  async updateTelemetry() {
    try {
      const response = await fetch('/last/telemetry');
      const data = await response.json();

      // Update telemetry data
      if (data.position) {
        this.telemetry.position = {
          latitude: parseFloat(data.position.latitude),
          longitude: parseFloat(data.position.longitude),
          altitude: parseFloat(data.position.altitude)
        };
      }

      if (data.battery) {
        this.telemetry.battery = {
          percentage: data.battery.percentage,
          id: data.battery.id
        };
      }

      if (data.flight_mode) {
        this.telemetry.flightMode = data.flight_mode.mode;
      }

      if (data.armed) {
        this.telemetry.armed = data.armed.armed;
      }

      if (data.in_air) {
        this.telemetry.inAir = data.in_air.in_air;
      }

      this.updateTelemetryUI();
      this.updateMapPosition();
      this.loading.telemetry = false;
      this.clearError();
    } catch (error) {
      console.error('Error fetching telemetry:', error);
      this.showError('Error al obtener telemetría');
    }
  }

  updateConnectionUI() {
    if (this.elements.status) {
      this.elements.status.className = `status-indicator ${this.connectionStatus.connected ? 'status-connected' : 'status-disconnected'}`;
    }

    if (this.elements.lastConnection) {
      this.elements.lastConnection.textContent = this.connectionStatus.lastConnection;
    }
  }

  updateTelemetryUI() {
    // Update position
    if (this.elements.latitude) {
      this.elements.latitude.textContent = this.telemetry.position.latitude !== null
        ? `${this.telemetry.position.latitude.toFixed(6)}°`
        : '---.------°';
    }

    if (this.elements.longitude) {
      this.elements.longitude.textContent = this.telemetry.position.longitude !== null
        ? `${this.telemetry.position.longitude.toFixed(6)}°`
        : '---.------°';
    }

    if (this.elements.altitude) {
      this.elements.altitude.textContent = this.telemetry.position.altitude !== null
        ? `${this.telemetry.position.altitude.toFixed(1)} m`
        : '--- m';
    }

    // Update battery
    if (this.elements.battery) {
      this.elements.battery.textContent = this.telemetry.battery.percentage !== null
        ? `${this.telemetry.battery.percentage}%`
        : '--%';
    }

    if (this.elements.batteryIcon && this.telemetry.battery.percentage !== null) {
      const percentage = this.telemetry.battery.percentage;
      this.elements.batteryIcon.textContent = percentage > 30 ? '🔋' : '🪫';
      this.elements.batteryIcon.className = `battery-icon ${percentage > 60 ? 'battery-good' :
        percentage > 30 ? 'battery-medium' :
          'battery-low'
        }`;
    }

    // Update flight mode
    if (this.elements.flightMode) {
      this.elements.flightMode.textContent = this.telemetry.flightMode || '---';
    }

    for (const button of this.elements.commandButtons) {
      if (button.value == FLIGHT_MODE_TO_COMMAND[this.telemetry.flightMode]) {
        button.classList.add("primary");
        button.classList.remove("secondary");
      } else {
        button.classList.remove("primary")
        button.classList.add("secondary")
      }
    }

    // Update armed status
    if (this.elements.armedStatus) {
      this.elements.armedStatus.checked = this.telemetry.armed
    }

    // Update in air status
    if (this.elements.airStatus) {
      this.elements.airStatus.checked = this.telemetry.inAir
    }
  }

  formatDateTime(date) {
    const options = {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    };
    return date.toLocaleDateString('es-MX', options);
  }

  showError(message) {
    this.error = message;
    if (this.elements.errorContainer) {
      this.elements.errorContainer.textContent = message;
      this.elements.errorContainer.style.display = 'block';
    }
  }

  clearError() {
    this.error = null;
    if (this.elements.errorContainer) {
      this.elements.errorContainer.style.display = 'none';
    }
  }

  initMap() {
    // Initialize the map centered on a default location (will update when we get GPS data)
    this.map = L.map('map').setView([19.4326, -99.1332], 13); // Default: Mexico City

    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(this.map);

    // Create custom drone icon
    const droneIcon = L.icon({
      iconUrl: '/static/img/drone-icon.svg',
      keyboard: false,
      iconSize: [50, 50],
      className: "drone-marker"
    });

    // Initialize drone marker (hidden initially)
    this.droneMarker = L.marker([0, 0], {
      icon: droneIcon
    });

    // Initialize trajectory polyline
    this.trajectory = L.polyline([], {
      color: '#2196f3',
      weight: 3,
      opacity: 0.8,
      className: 'trajectory-line'
    }).addTo(this.map);
  }

  updateMapPosition() {
    const { latitude, longitude } = this.telemetry.position;

    if (latitude !== null && longitude !== null) {
      const newLatLng = [latitude, longitude];

      // Add marker to map if not already added
      if (!this.droneMarker.getLatLng() || (this.droneMarker.getLatLng().lat === 0 && this.droneMarker.getLatLng().lng === 0)) {
        this.droneMarker.addTo(this.map);
        this.map.setView(newLatLng, 16); // Center map on first position
      }

      // Update marker position
      this.droneMarker.setLatLng(newLatLng);

      // Update marker style based on armed status
      const markerElement = this.droneMarker.getElement();
      if (markerElement) {
        if (this.telemetry.armed) {
          markerElement.classList.add('drone-marker-armed');
        } else {
          markerElement.classList.remove('drone-marker-armed');
        }
      }

      // Add point to trajectory
      this.trajectoryPoints.push(newLatLng);

      // Limit trajectory points
      if (this.trajectoryPoints.length > this.maxTrajectoryPoints) {
        this.trajectoryPoints.shift();
      }

      // Update trajectory line
      this.trajectory.setLatLngs(this.trajectoryPoints);

      // Pan to drone if it's moving out of view
      if (!this.map.getBounds().contains(newLatLng)) {
        this.map.panTo(newLatLng);
      }
    }
  }

  clearTrajectory() {
    this.trajectoryPoints = [];
    this.trajectory.setLatLngs([]);
  }

  centerOnDrone() {
    const { latitude, longitude } = this.telemetry.position;
    if (latitude !== null && longitude !== null) {
      this.map.setView([latitude, longitude], 16);
    }
  }

  destroy() {
    if (this.connectionInterval) {
      clearInterval(this.connectionInterval);
    }
    if (this.telemetryInterval) {
      clearInterval(this.telemetryInterval);
    }
    if (this.map) {
      this.map.remove();
    }
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.droneControl = new DroneControl();
});
