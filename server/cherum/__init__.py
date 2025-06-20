from cherum.telemetry_store import TelemetryStore
from flask import Flask, render_template, request, redirect, jsonify
import cherum.jwt as jwt
import cherum.db as db
import datetime
import os
import asyncio

central_mexico_utc_offset = datetime.timedelta(hours=-6)
central_mexico_tz = datetime.timezone(central_mexico_utc_offset)
utc_tz = datetime.timezone.utc


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        APP_NAME='Cherum',
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
        INFLUXDB_URL='http://localhost:8086',
        INFLUXDB_TOKEN='dev',
        INFLUXDB_ORG='covenant',
        INFLUXDB_BUCKET='telemetry',
        VIDEO_URL='http://localhost:8889/mystream/whep'
    )
    app.teardown_appcontext(db.close)
    app.cli.add_command(db.init_db_command)
    app.cli.add_command(jwt.create_token_command)

    run_in_container = os.environ.get("CONTAINER", None)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    if run_in_container == "docker":
        app.config.from_mapping(os.environ)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    telemetry_store = TelemetryStore(
        url=app.config['INFLUXDB_URL'],
        token=app.config['INFLUXDB_TOKEN'],
        org=app.config['INFLUXDB_ORG'],
        bucket=app.config['INFLUXDB_BUCKET']
    )
    app.teardown_appcontext(telemetry_store.close)

    # a simple page that says hello
    @app.route('/health')
    def health():
        return 'OK'

    @app.route('/', methods=["GET"])
    def index():
        last_connection = "Never"

        conn_q = db.get().execute(
            "SELECT created_at FROM pings ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if conn_q is not None:
            last_connection = conn_q[0]
            last_connection = datetime.datetime(
                last_connection.year,
                last_connection.month,
                last_connection.day,
                last_connection.hour,
                last_connection.minute,
                last_connection.second,
                tzinfo=utc_tz
            )

            inactivity = datetime.datetime.now(utc_tz) - last_connection
            if inactivity.seconds > 10:
                last_command = None

            last_connection = last_connection.astimezone(central_mexico_tz) \
                .strftime("%d/%m/%Y %H:%M:%S")
        return render_template("index.html", last_connection=last_connection, video_url=app.config["VIDEO_URL"])

    @app.route('/last/connection')
    def last_connection():
        conn_q = db.get().execute(
            "SELECT created_at FROM pings ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if conn_q is not None:
            last_connection = conn_q[0]
            last_connection = datetime.datetime(
                last_connection.year,
                last_connection.month,
                last_connection.day,
                last_connection.hour,
                last_connection.minute,
                last_connection.second,
                tzinfo=utc_tz
            )
            return str(last_connection.astimezone(central_mexico_tz))
        return "Never"

    @app.route('/command', methods=["POST"])
    def command():
        command = request.form.get("command")
        if command:
            db.get().execute(
                "INSERT INTO commands (command, done) VALUES (?, ?)",
                (command, 0)
            )
            db.get().commit()
        return redirect("/")

    @app.route('/fetch')
    def fetch():
        if jwt.get_and_validate_token() is None:
            return {"error": "Unauthorized"}, 401
        query = db.get().execute(
            "SELECT * FROM commands ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if query is None:
            response = {"id": None, "command": "", "done": 1}
        else:
            response = {"id": query[0], "command": query[1], "done": query[2]}
        query = db.get().execute(
            "INSERT INTO pings (created_at) VALUES (CURRENT_TIMESTAMP)"
        )
        db.get().commit()
        return response

    @app.route('/done/<int:id>', methods=["POST"])
    def done(id):
        if jwt.get_and_validate_token() is None:
            return {"error": "Unauthorized"}, 401
        db.get().execute(
            "UPDATE commands SET done = 1 WHERE id = ?",
            (id,)
        )
        db.get().commit()
        return {"id": id}

    @app.route('/last/telemetry', methods=["GET"])
    async def last_telemetry():
        drone_id = request.args.get('drone_id', 'default')
        tasks = [
            asyncio.create_task(telemetry_store.last_position(drone_id)),
            asyncio.create_task(telemetry_store.last_battery(drone_id)),
            asyncio.create_task(telemetry_store.last_flight_mode(drone_id)),
            asyncio.create_task(telemetry_store.last_armed(drone_id)),
            asyncio.create_task(telemetry_store.last_in_air(drone_id))
        ]
        results = await asyncio.gather(*tasks)
        return {
            "position": results[0],
            "battery": results[1],
            "flight_mode": results[2],
            "armed": results[3],
            "in_air": results[4]
        }

    @app.route('/telemetry', methods=["POST", "GET"])
    async def telemetry():
        if request.method == "GET":
            minutes = request.args.get('minutes', 10, type=int)
            drone_id = request.args.get('drone_id', 'default')

            try:
                positions = telemetry_store.query_recent_positions(
                    minutes=minutes, drone_id=drone_id)
                return jsonify(positions), 200
            except Exception as e:
                app.logger.error(f"Error querying telemetry: {e}")
                return {"error": "Failed to query telemetry"}, 500

        if jwt.get_and_validate_token() is None:
            return {"error": "Unauthorized"}, 401

        data = request.json
        if not data or 'type' not in data:
            return {"error": "Invalid telemetry data"}, 400

        try:
            if telemetry_store:
                drone_id = data.get('drone_id', 'default')

                if data['type'] == 'position':
                    pos_data = data['data']
                    await telemetry_store.store_position(
                        lat=float(pos_data['latitude_deg']),
                        lon=float(pos_data['longitude_deg']),
                        alt=float(pos_data['relative_altitude_m']),
                        drone_id=drone_id
                    )

                elif data['type'] == 'battery':
                    bat_data = data['data']
                    await telemetry_store.store_battery(
                        battery_id=bat_data['id'],
                        percent=bat_data['remaining_percent'],
                        drone_id=drone_id
                    )

                elif data['type'] == 'flight_mode':
                    mode_data = data['data']
                    await telemetry_store.store_flight_mode(
                        mode=mode_data['mode'],
                        drone_id=drone_id
                    )

                elif data['type'] == 'armed':
                    armed = data['armed']
                    await telemetry_store.store_armed(armed, drone_id)

                elif data['type'] == 'in_air':
                    in_air = data['in_air']
                    await telemetry_store.store_in_air(in_air, drone_id)

            return {"status": "received"}, 200

        except Exception as e:
            app.logger.error(f"Error storing telemetry: {e}")
            return {"error": "Failed to store telemetry"}, 500

    return app
