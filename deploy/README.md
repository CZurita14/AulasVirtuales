# Despliegue en la red de la universidad

Destino: `https://cia.indoamerica.edu.ec/aulasvirtuales/`.

El DNS interno debe resolver `cia.indoamerica.edu.ec` a la IP interna del servidor. No se requiere publicar el servidor en Internet.

1. Instalar Docker y Docker Compose desde los repositorios del sistema operativo.
2. Clonar el repositorio en `/home/uti/aulasvirtuales`.
3. Copiar `.env.example` a `.env`, configurar Qwen y restringir los permisos del archivo a su propietario.
4. Ejecutar `sudo docker compose up -d --build` desde la carpeta del proyecto.
5. Copiar `nginx-aulasvirtuales.conf` a `/etc/nginx/snippets/aulasvirtuales.conf` e incluirlo dentro del bloque `server` HTTPS del dominio.
6. Validar con `sudo nginx -t` y recargar con `sudo systemctl reload nginx`.

Los puertos de la aplicación se mantienen vinculados a `127.0.0.1`; Qdrant no publica puertos. Nginx conserva el certificado y los demás servicios existentes del dominio.

Comprobación local del dominio mientras se configura DNS:

```bash
curl --resolve cia.indoamerica.edu.ec:443:127.0.0.1 https://cia.indoamerica.edu.ec/aulasvirtuales/api/salud
```

La aplicación debe funcionar también en `/` para el acceso local. La prueba `sistema/tests/test_ruta_publica.py` verifica las operaciones de JavaScript en ambas rutas; requiere Node.js solo para ejecutar esa prueba.
