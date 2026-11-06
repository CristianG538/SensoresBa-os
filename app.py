#!/usr/bin/env python3
"""
Receptor HTTP para el sensor Minew MSR01 (Wi-Fi), listo para hosting gratuito.

Rutas:
  POST/PUT  /msr01           -> el sensor envia aqui (cualquier ruta que no sea /api/* tambien sirve)
  GET       /                -> interfaz visual en vivo
  GET       /api/mensajes    -> ultimos mensajes en JSON
  GET       /api/descargar   -> descarga de todos los mensajes (.jsonl)
  POST      /api/limpiar     -> borra los mensajes de la memoria
  GET       /salud           -> chequeo de vida para el host

Variables de entorno (opcionales):
  PORT       puerto (el host lo define solo; local = 8080)
  TOKEN      si se define, el sensor debe enviar a /msr01?token=XXXX y la interfaz pide el token
  MAX_MSG    cuantos mensajes guardar en memoria (por defecto 500)

Solo libreria estandar de Python 3.
"""

import json
import os
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT", "8080"))
TOKEN = os.environ.get("TOKEN", "").strip()
MAX_MSG = int(os.environ.get("MAX_MSG", "500"))
ARCHIVO = Path("datos_sensor.jsonl")
BOGOTA = timezone(timedelta(hours=-5))
INDEX = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")

mensajes = deque(maxlen=MAX_MSG)
estado = {"total": 0, "inicio": datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")}
candado = threading.Lock()
seq = 0


class Manejador(BaseHTTPRequestHandler):
    server_version = "MSR01-Receptor/1.0"

    # ---------- utilidades ----------
    def _enviar(self, codigo, cuerpo, tipo="application/json", extra=None):
        datos = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(datos)

    def _token_ok(self, url):
        if not TOKEN:
            return True
        q = parse_qs(url.query)
        return (q.get("token", [""])[0] == TOKEN
                or self.headers.get("X-Token", "") == TOKEN)

    def _ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() if fwd else self.client_address[0]

    # ---------- GET ----------
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            return self._enviar(200, INDEX, "text/html")
        if url.path == "/salud":
            return self._enviar(200, '{"ok":true}')
        if url.path.startswith("/api/"):
            if not self._token_ok(url):
                return self._enviar(401, '{"error":"token invalido"}')
            if url.path == "/api/mensajes":
                desde = int(parse_qs(url.query).get("desde", ["0"])[0] or 0)
                with candado:
                    nuevos = [m for m in mensajes if m["id"] > desde]
                    cuerpo = json.dumps({**estado, "protegido": bool(TOKEN),
                                         "mensajes": nuevos}, ensure_ascii=False)
                return self._enviar(200, cuerpo)
            if url.path == "/api/descargar":
                with candado:
                    lineas = "\n".join(json.dumps(m, ensure_ascii=False) for m in reversed(mensajes))
                return self._enviar(200, lineas + "\n", "application/x-ndjson",
                                    {"Content-Disposition": "attachment; filename=msr01.jsonl"})
            return self._enviar(404, '{"error":"no encontrado"}')
        # Algunos equipos hacen GET al probar el servidor: lo registramos tambien
        return self._recibir()

    do_HEAD = do_GET

    # ---------- POST / PUT ----------
    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/limpiar":
            if not self._token_ok(url):
                return self._enviar(401, '{"error":"token invalido"}')
            with candado:
                mensajes.clear()
            return self._enviar(200, '{"ok":true}')
        return self._recibir()

    do_PUT = do_POST

    def _recibir(self):
        global seq
        url = urlparse(self.path)
        if not self._token_ok(url):
            return self._enviar(401, '{"error":"token invalido"}')

        largo = int(self.headers.get("Content-Length", 0) or 0)
        crudo_b = self.rfile.read(largo) if largo else b""
        crudo = crudo_b.decode("utf-8", errors="replace")
        try:
            parseado = json.loads(crudo) if crudo else None
            es_json = crudo != ""
        except json.JSONDecodeError:
            parseado, es_json = None, False

        encabezados = {k: v for k, v in self.headers.items()
                       if not k.lower().startswith(("x-forwarded", "x-real", "cf-", "rndr", "true-client"))}

        with candado:
            seq += 1
            registro = {
                "id": seq,
                "hora": datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S"),
                "ip": self._ip(),
                "metodo": self.command,
                "ruta": url.path,
                "consulta": url.query.replace(f"token={TOKEN}", "token=***") if TOKEN else url.query,
                "bytes": largo,
                "tipo": self.headers.get("Content-Type", ""),
                "es_json": es_json,
                "encabezados": encabezados,
                "crudo": crudo,           # exactamente lo que llego
                "json": parseado,         # el mismo cuerpo, interpretado (si era JSON)
            }
            mensajes.appendleft(registro)
            estado["total"] += 1
            try:
                with ARCHIVO.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            except OSError:
                pass

        print(f"[{registro['hora']}] {self.command} {url.path} {largo}B desde {registro['ip']}: {crudo[:500]}",
              flush=True)
        # Respuesta simple; muchos equipos solo esperan un 200
        return self._enviar(200, '{"code":200,"msg":"ok"}')

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Receptor MSR01 escuchando en el puerto {PORT}"
          + (" (protegido con TOKEN)" if TOKEN else ""), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Manejador).serve_forever()
