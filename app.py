import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mvp-incidentes-educativos-clave")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "incidentes.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE,
                titulo TEXT NOT NULL,
                categoria TEXT NOT NULL DEFAULT 'Infraestructura / Aula',
                sede_o_espacio TEXT NOT NULL DEFAULT 'Bloque A - Aula 101',
                descripcion TEXT NOT NULL,
                prioridad TEXT NOT NULL DEFAULT 'Media',
                estado TEXT NOT NULL DEFAULT 'Registrado',
                asignado_a TEXT NOT NULL DEFAULT 'Soporte Técnico / Medios Audiovisuales',
                reportado_por TEXT NOT NULL DEFAULT 'Docente / Coordinador',
                observaciones TEXT DEFAULT '',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def generar_codigo(incidente_id: int) -> str:
    return f"INC-{incidente_id:03d}"


def contexto_sesion():
    return {
        "usuario": session.get("usuario", "Usuario de Prueba"),
        "rol": session.get("rol", "Coordinador / Soporte"),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip() or "Usuario de Prueba"
        rol = request.form.get("rol", "").strip() or "Coordinador / Soporte"
        session["usuario"] = usuario
        session["rol"] = rol
        return redirect(url_for("dashboard"))
    return render_template("login.html", **contexto_sesion())


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))


@app.route("/")
@app.route("/dashboard")
def dashboard():
    estado_filtro = request.args.get("estado", "Todos").strip()
    prioridad_filtro = request.args.get("prioridad", "Todas").strip()

    query = "SELECT * FROM incidentes WHERE 1=1"
    params = []

    if estado_filtro and estado_filtro != "Todos":
        query += " AND estado = ?"
        params.append(estado_filtro)

    if prioridad_filtro and prioridad_filtro != "Todas":
        query += " AND prioridad = ?"
        params.append(prioridad_filtro)

    query += " ORDER BY id DESC"

    with get_db() as conn:
        incidentes = conn.execute(query, params).fetchall()
        totales = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN estado = 'Registrado' THEN 1 ELSE 0 END) AS registrados,
                SUM(CASE WHEN estado = 'En atención' THEN 1 ELSE 0 END) AS en_atencion,
                SUM(CASE WHEN estado = 'Resuelto' THEN 1 ELSE 0 END) AS resueltos
            FROM incidentes
            """
        ).fetchone()

    return render_template(
        "dashboard.html",
        incidentes=incidentes,
        totales=totales,
        estado_filtro=estado_filtro,
        prioridad_filtro=prioridad_filtro,
        **contexto_sesion(),
    )


@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    ctx = contexto_sesion()
    error = None

    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        categoria = request.form.get("categoria", "Infraestructura / Aula").strip()
        sede_o_espacio = request.form.get("sede_o_espacio", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        prioridad = request.form.get("prioridad", "Media").strip()
        asignado_a = request.form.get(
            "asignado_a", "Soporte Técnico / Medios Audiovisuales"
        ).strip()
        reportado_por = request.form.get("reportado_por", "").strip() or ctx["usuario"]
        estado = "Registrado"

        if not titulo or not descripcion:
            error = "Por favor completa al menos el título y la descripción del incidente."
        else:
            espacio_final = sede_o_espacio or "Espacio educativo por confirmar"
            with get_db() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO incidentes (
                        titulo, categoria, sede_o_espacio, descripcion,
                        prioridad, estado, asignado_a, reportado_por
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        titulo,
                        categoria,
                        espacio_final,
                        descripcion,
                        prioridad,
                        estado,
                        asignado_a,
                        reportado_por,
                    ),
                )
                nuevo_id = cursor.lastrowid
                codigo = generar_codigo(nuevo_id)
                conn.execute(
                    "UPDATE incidentes SET codigo = ? WHERE id = ?",
                    (codigo, nuevo_id),
                )
                conn.commit()
            return redirect(url_for("dashboard"))

    return render_template("registrar.html", error=error, **ctx)


@app.route("/incidente/<int:incidente_id>", methods=["GET", "POST"])
def detalle(incidente_id):
    ctx = contexto_sesion()

    with get_db() as conn:
        if request.method == "POST":
            nuevo_estado = request.form.get("estado", "Registrado").strip()
            nueva_prioridad = request.form.get("prioridad", "Media").strip()
            nuevo_asignado = request.form.get(
                "asignado_a", "Soporte Técnico / Medios Audiovisuales"
            ).strip()
            observaciones = request.form.get("observaciones", "").strip()

            conn.execute(
                """
                UPDATE incidentes
                SET estado = ?,
                    prioridad = ?,
                    asignado_a = ?,
                    observaciones = ?,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (nuevo_estado, nueva_prioridad, nuevo_asignado, observaciones, incidente_id),
            )
            conn.commit()
            return redirect(url_for("detalle", incidente_id=incidente_id))

        incidente = conn.execute(
            "SELECT * FROM incidentes WHERE id = ?", (incidente_id,)
        ).fetchone()

    if incidente is None:
        return redirect(url_for("dashboard"))

    return render_template("detalle.html", incidente=incidente, **ctx)


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
