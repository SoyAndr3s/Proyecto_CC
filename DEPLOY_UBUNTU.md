# Instalación local en Ubuntu Desktop 26.04

Esta guía cubre únicamente la ejecución local del prototipo en una computadora Ubuntu. No configura servidores remotos ni publicación en Internet.

## Requisitos e instalación

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd /ruta/a/ProjectCC_v5_1/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `backend/.env` y configura una `SECRET_KEY` aleatoria propia. Para pruebas locales conserva `APP_ENV=development`.

## Primera ejecución

```bash
python create_admin.py
python app.py
```

Abre `http://127.0.0.1:8080/login.html`. El servidor de desarrollo escucha en loopback y no está pensado para exponerlo a otras computadoras.

## Actualización desde v5.0

1. Detén el sistema.
2. Haz una copia de `backend/custodia.db` y de `backend/uploads/`.
3. Sustituye los archivos de la aplicación por la versión 5.1 sin eliminar la base de datos ni la carpeta `uploads`.
4. Activa el entorno virtual e inicia `python app.py`. La migración incremental se ejecuta al cargar la aplicación.
5. Comprueba los indicios, responsables y entregas pendientes antes de continuar las pruebas.

## Copias de seguridad

Respalda juntos `backend/custodia.db` y `backend/uploads/`, ya que la base contiene las rutas de las fotografías y firmas. Guarda las copias en un medio cifrado y comprueba periódicamente que puedan restaurarse.
