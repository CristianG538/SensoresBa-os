# Monitor MSR01

Receptor HTTP para el sensor Minew MSR01 (Wi-Fi) con interfaz visual que muestra
**exactamente** lo que envía el sensor: cuerpo crudo, JSON formateado y encabezados.

## Estructura

```
servidor-msr01/
├── app.py              # Servidor (solo Python estándar, sin dependencias)
├── static/
│   └── index.html      # Interfaz visual en vivo
├── requirements.txt    # Vacío a propósito (Render lo exige)
├── render.yaml         # Configuración para desplegar en Render
├── Procfile            # Para otros hosts (Railway, Koyeb, Heroku)
├── .python-version     # Versión de Python
├── .gitignore
└── README.md
```

## Probar en el PC

```
python app.py
```
Abre http://localhost:8080 y simula un envío del sensor:
```
curl -X POST http://localhost:8080/msr01 -H "Content-Type: application/json" -d "{\"in\":3,\"out\":2}"
```

## Subir a Render (gratis)

1. Crea una cuenta en https://github.com y un repositorio nuevo (ej. `monitor-msr01`).
2. Sube todos estos archivos al repositorio (botón **Add file → Upload files**,
   arrastra el contenido de la carpeta, incluida la carpeta `static`).
3. Crea una cuenta en https://render.com (puedes entrar con GitHub).
4. **New → Blueprint**, elige el repositorio. Render lee `render.yaml` y crea el servicio.
   - Te pedirá `TOKEN`: escribe una clave (ej. `opain2026`) o déjalo vacío.
5. Espera el despliegue (2–3 min). Tu URL será algo como
   `https://monitor-msr01.onrender.com`.

## Configurar el sensor (MinewLink)

- Protocolo: **HTTP**
- URL: `https://monitor-msr01.onrender.com/msr01`
  (si definiste TOKEN: `https://monitor-msr01.onrender.com/msr01?token=TU_TOKEN`)
- Usa **https**: Render redirige http → https y algunos equipos no siguen la redirección en un POST.
- Confirm → Restart.

Luego abre `https://monitor-msr01.onrender.com` para ver los mensajes en vivo.

## Limitaciones del plan gratis de Render

- El servicio **se duerme tras 15 min sin tráfico** y tarda ~1 min en despertar.
  Si el sensor envía datos cada pocos minutos, se mantiene despierto.
- **No hay disco persistente**: al reiniciarse se pierden los mensajes guardados.
  Usa el botón **Descargar .jsonl** para guardar lo que necesites.
- 750 horas gratis al mes por cuenta (alcanza para un servicio 24/7).

Esto es para **pruebas e identificación del formato**. Para producción, los datos
deben ir a Aluna.

## Rutas

| Ruta | Uso |
|---|---|
| `POST /msr01` | El sensor envía aquí (cualquier otra ruta fuera de `/api/` también se registra) |
| `GET /` | Interfaz visual |
| `GET /api/mensajes` | Mensajes en JSON |
| `GET /api/descargar` | Descarga `.jsonl` |
| `POST /api/limpiar` | Borra los mensajes en memoria |
| `GET /salud` | Chequeo del host |
