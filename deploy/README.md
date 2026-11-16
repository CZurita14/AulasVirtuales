# Despliegue en la red de la universidad

Destino: `https://cia.indoamerica.edu.ec/aulasvirtuales/`.

El DNS interno debe resolver `cia.indoamerica.edu.ec` a la IP interna del servidor. No se requiere publicar el servidor en Internet.

1. Instalar Docker y Docker Compose desde los repositorios del sistema operativo.
2. Clonar el repositorio en `/home/uti/aulasvirtuales`.
3. Copiar `.env.example` a `.env`, configurar Qwen y restringir los permisos del archivo a su propietario. **Definir `HISTORIAL_CLAVE`** (o `HISTORIAL=0`): sin clave, el historial queda cerrado (403). No poner `HISTORIAL_LOCAL=1` en el servidor.
4. Ejecutar `sudo docker compose up -d --build` desde la carpeta del proyecto.
5. Copiar `nginx-aulasvirtuales.conf` a `/etc/nginx/snippets/aulasvirtuales.conf` e incluirlo dentro del bloque `server` HTTPS del dominio.
6. Validar con `sudo nginx -t` y recargar con `sudo systemctl reload nginx`.

Los puertos de la aplicación se mantienen vinculados a `127.0.0.1`; Qdrant no publica puertos. Nginx conserva el certificado y los demás servicios existentes del dominio.

La red de Compose usa `192.168.240.0/24` para evitar el rango universitario `172.18.0.0/16`. Antes de desplegar en otro servidor, comprobar con `ip route` que esa subred también esté libre allí.

Comprobación local del dominio mientras se configura DNS:

```bash
curl --resolve cia.indoamerica.edu.ec:443:127.0.0.1 https://cia.indoamerica.edu.ec/aulasvirtuales/api/salud
```

La aplicación debe funcionar también en `/` para el acceso local. La prueba `sistema/tests/test_ruta_publica.py` verifica las operaciones de JavaScript en ambas rutas; requiere Node.js solo para ejecutar esa prueba.

## Dirección fija desde este equipo (Tailscale Funnel)

Mientras la UTI no lo instale en su servidor, el sistema puede publicarse desde este equipo con una dirección HTTPS
**fija** (`https://aulasvirtuales.<tu-tailnet>.ts.net`), que no cambia al reiniciar.

```bash
docker compose --profile publico up -d
```

- La primera vez, `docker logs aulasvirtuales-silabos-funnel-1` muestra el enlace para iniciar sesión en Tailscale, y
  hay que activar **HTTPS y Funnel** en la red de Tailscale (el propio comando `tailscale funnel` da el enlace).
- La identidad se guarda en el volumen `tailscale_estado`: **no** borrarlo o la dirección cambia.
- `deploy/tailscale/funnel.json` envía todo a `http://app:8770`. El Historial sigue cerrado desde fuera (pasa por proxy).
- Vigilante: `deploy/vigilar_tunel.ps1` (tarea programada cada 5 min) levanta la app o el puente si dejan de responder y
  anota en `datos/vigilancia.log`.
- Para cerrarlo: `docker compose stop funnel`.
- No escribir la dirección pública en archivos del repo (es público): se comparte por chat.
