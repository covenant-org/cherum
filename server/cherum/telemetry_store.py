from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS


class TelemetryStore:
    """Efficient storage for drone telemetry using InfluxDB."""

    def __init__(self, url: str = "http://localhost:8086",
                 token: str = "your-token-here",
                 org: str = "cherum",
                 bucket: str = "drone_telemetry"):
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
        self.bucket = bucket
        self.org = org

        # Buffer for batch writes (more efficient)
        self.buffer = []
        self.buffer_size = 100  # Write every 100 points
        self.last_flush = datetime.now()
        self.flush_interval = 5  # Flush every 5 seconds

    async def store_position(self, lat: float, lon: float, alt: float,
                             drone_id: str = "default"):
        """Store position data with automatic batching."""
        point = Point("position") \
            .tag("drone_id", drone_id) \
            .field("latitude", lat) \
            .field("longitude", lon) \
            .field("altitude", alt) \
            .time(datetime.utcnow())

        self.buffer.append(point)
        await self._check_flush()

    async def store_battery(self, battery_id: int, percent: float,
                            drone_id: str = "default"):
        """Store battery telemetry."""
        point = Point("battery") \
            .tag("drone_id", drone_id) \
            .tag("battery_id", str(battery_id)) \
            .field("remaining_percent", percent) \
            .time(datetime.utcnow())

        self.buffer.append(point)
        await self._check_flush()

    async def store_flight_mode(self, mode: str, drone_id: str = "default"):
        """Store flight mode changes."""
        point = Point("flight_mode") \
            .tag("drone_id", drone_id) \
            .field("mode", mode) \
            .time(datetime.utcnow())

        self.buffer.append(point)
        await self._check_flush()

    async def _check_flush(self):
        """Flush buffer if size or time threshold is reached."""
        time_since_flush = (datetime.now() - self.last_flush).seconds

        if len(self.buffer) >= self.buffer_size or time_since_flush >= self.flush_interval:
            await self.flush()

    async def flush(self):
        """Write buffered data to InfluxDB."""
        if self.buffer:
            try:
                self.write_api.write(bucket=self.bucket, org=self.org,
                                     record=self.buffer)
                self.buffer = []
                self.last_flush = datetime.now()
            except Exception as e:
                print(f"Error writing to InfluxDB: {e}")

    def query_recent_positions(self, minutes: int = 10,
                               drone_id: str = "default") -> list:
        """Query recent positions for analysis."""
        query_api = self.client.query_api()

        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r["_measurement"] == "position")
          |> filter(fn: (r) => r["drone_id"] == "{drone_id}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
        '''

        result = query_api.query(org=self.org, query=query)
        positions = []

        for table in result:
            for record in table.records:
                positions.append({
                    'time': record.get_time(),
                    'latitude': record.values.get('latitude'),
                    'longitude': record.values.get('longitude'),
                    'altitude': record.values.get('altitude')
                })

        return positions

    def query_positions_in_area(self, min_lat: float, max_lat: float,
                                min_lon: float, max_lon: float,
                                hours: int = 24) -> list:
        """Query positions within a geographic bounding box."""
        query_api = self.client.query_api()

        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "position")
          |> filter(fn: (r) => r["_field"] == "latitude" or 
                              r["_field"] == "longitude" or 
                              r["_field"] == "altitude")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> filter(fn: (r) => r.latitude >= {min_lat} and r.latitude <= {max_lat})
          |> filter(fn: (r) => r.longitude >= {min_lon} and r.longitude <= {max_lon})
          |> sort(columns: ["_time"], desc: true)
        '''

        result = query_api.query(org=self.org, query=query)
        positions = []

        for table in result:
            for record in table.records:
                positions.append({
                    'time': record.get_time(),
                    'latitude': record.values.get('latitude'),
                    'longitude': record.values.get('longitude'),
                    'altitude': record.values.get('altitude')
                })

        return positions

    async def close(self):
        """Clean up resources."""
        await self.flush()
        self.client.close()
