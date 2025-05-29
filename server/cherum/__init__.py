import os
import datetime
import cherum.db as db
import cherum.jwt as jwt
from flask import Flask, render_template, request, redirect

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
    )
    app.teardown_appcontext(db.close)
    app.cli.add_command(db.init_db_command)
    app.cli.add_command(jwt.create_token_command)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/health')
    def health():
        return 'OK'

    @app.route('/', methods=["GET", "POST"])
    def index():
        last_connection = "Never"
        comand_q = db.get().execute(
            "SELECT command FROM commands ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
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
            last_connection = last_connection.astimezone(central_mexico_tz) \
                .strftime("%d/%m/%Y %H:%M:%S")
        return render_template("index.html", last_connection=last_connection, last_command=comand_q[0])

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

    return app
