import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "clave-secreta-mvp-incidentes-trl5"
DB_NAME = "incidentes.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla de usuarios para autenticación real con contraseñas hasheadas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # Tabla de incidentes educativos (conserva la estructura actual)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE,
            titulo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            espacio TEXT NOT NULL,
            prioridad TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Registrado',
            asignado_a TEXT NOT NULL,
            reportado_por TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            observaciones TEXT DEFAULT '',
            fecha_registro TEXT NOT NULL
        )
    """)

    # Insertar los 3 usuarios de prueba si aún no existen
    usuarios_iniciales = [
        ("admin", "Administrador", "Rol Administrador", generate_password_hash("1234")),
        ("analista", "Analista", "Rol Administrador", generate_password_hash("1234")),
        ("soporte", "Soporte", "Rol Usuario", generate_password_hash("1234")),
    ]
    for username, nombre, rol, pw_hash in usuarios_iniciales:
        cursor.execute(
            "INSERT OR IGNORE INTO usuarios (username, nombre, rol, password_hash) VALUES (?, ?, ?, ?)",
            (username, nombre, rol, pw_hash),
        )

    conn.commit()
    conn.close()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["usuario"] = user["nombre"]
            session["rol"] = user["rol"]
            return redirect(url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@app.route("/restablecer-clave", methods=["POST"])
def restablecer_clave():
    username = request.form.get("reset_username", "").strip().lower()
    nueva_clave = request.form.get("nueva_clave", "")
    confirmar_clave = request.form.get("confirmar_clave", "")

    if not username or not nueva_clave:
        flash("Debes ingresar el usuario y la nueva contraseña.", "danger")
        return redirect(url_for("login"))

    if nueva_clave != confirmar_clave:
        flash("Las contraseñas no coinciden.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id FROM usuarios WHERE username = ?", (username,)
    ).fetchone()

    if not user:
        conn.close()
        flash("El usuario ingresado no existe.", "danger")
        return redirect(url_for("login"))

    conn.execute(
        "UPDATE usuarios SET password_hash = ? WHERE username = ?",
        (generate_password_hash(nueva_clave), username),
    )
    conn.commit()
    conn.close()

    flash(f"Contraseña actualizada correctamente para '{username}'. Ya puedes ingresar.", "success")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    estado_filtro = request.args.get("estado", "Todos")
    prioridad_filtro = request.args.get("prioridad", "Todas")

    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0]
    registrados = conn.execute("SELECT COUNT(*) FROM incidentes WHERE estado = 'Registrado'").fetchone()[0]
    en_atencion = conn.execute("SELECT COUNT(*) FROM incidentes WHERE estado = 'En atención'").fetchone()[0]
    resueltos = conn.execute("SELECT COUNT(*) FROM incidentes WHERE estado = 'Resuelto'").fetchone()[0]

    query = "SELECT * FROM incidentes WHERE 1=1"
    params = []

    if estado_filtro and estado_filtro != "Todos":
        query += " AND estado = ?"
        params.append(estado_filtro)

    if prioridad_filtro and prioridad_filtro != "Todas":
        query += " AND prioridad = ?"
        params.append(prioridad_filtro)

    query += " ORDER BY id DESC"
    incidentes = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "dashboard.html",
        incidentes=incidentes,
        total=total,
        registrados=registrados,
        en_atencion=en_atencion,
        resueltos=resueltos,
        estado_filtro=estado_filtro,
        prioridad_filtro=prioridad_filtro,
        usuario=session.get("usuario"),
        rol=session.get("rol"),
    )


@app.route("/registrar", methods=["GET", "POST"])
@login_required
def registrar():
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        categoria = request.form.get("categoria", "Infraestructura / Aula")
        espacio = request.form.get("espacio", "").strip()
        prioridad = request.form.get("prioridad", "Media")
        asignado_a = request.form.get("asignado_a", "Soporte Técnico / Medios Audiovisuales").strip()
        reportado_por = request.form.get("reportado_por", session.get("usuario", "Usuario")).strip()
        descripcion = request.form.get("descripcion", "").strip()
        fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if titulo and descripcion:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO incidentes
                (titulo, categoria, espacio, prioridad, estado, asignado_a, reportado_por, descripcion, fecha_registro)
                VALUES (?, ?, ?, ?, 'Registrado', ?, ?, ?, ?)
                """,
                (titulo, categoria, espacio or "General", prioridad, asignado_a, reportado_por, descripcion, fecha_registro),
            )
            nuevo_id = cursor.lastrowid
            codigo = f"INC-{nuevo_id:03d}"
            cursor.execute("UPDATE incidentes SET codigo = ? WHERE id = ?", (codigo, nuevo_id))
            conn.commit()
            conn.close()
            return redirect(url_for("index"))

    return render_template(
        "registrar.html",
        usuario=session.get("usuario"),
        rol=session.get("rol"),
    )


@app.route("/incidente/<int:incidente_id>", methods=["GET", "POST"])
@login_required
def detalle(incidente_id):
    conn = get_db_connection()
    incidente = conn.execute("SELECT * FROM incidentes WHERE id = ?", (incidente_id,)).fetchone()

    if not incidente:
        conn.close()
        return redirect(url_for("index"))

    if request.method == "POST":
        nuevo_estado = request.form.get("estado", incidente["estado"])
        nueva_prioridad = request.form.get("prioridad", incidente["prioridad"])
        nuevo_asignado = request.form.get("asignado_a", incidente["asignado_a"]).strip()
        observaciones = request.form.get("observaciones", "").strip()

        conn.execute(
            """
            UPDATE incidentes
            SET estado = ?, prioridad = ?, asignado_a = ?, observaciones = ?
            WHERE id = ?
            """,
            (nuevo_estado, nueva_prioridad, nuevo_asignado, observaciones, incidente_id),
        )
        conn.commit()
        incidente = conn.execute("SELECT * FROM incidentes WHERE id = ?", (incidente_id,)).fetchone()

    conn.close()
    return render_template(
        "detalle.html",
        incidente=incidente,
        usuario=session.get("usuario"),
        rol=session.get("rol"),
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
