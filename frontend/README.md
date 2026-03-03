# Dashboard React (Gestor de Lockers)

Esta carpeta es el **frontend del dashboard** (React + Vite + Tailwind). Hay que instalar dependencias y generar el build para que Flask lo sirva.

## Requisito: Node.js

Si no lo tienes, descárgalo e instálalo desde: **https://nodejs.org** (versión LTS). Cierra y vuelve a abrir la terminal después de instalar.

---

## Opción 1: Desde la raíz del proyecto (recomendado)

En la carpeta del proyecto **gestor_lockers** (donde está `run.py`), haz doble clic en:

**`build_dashboard.bat`**

Ese script entra en `frontend`, ejecuta `npm install` y `npm run build`. Si algo falla, te dirá si falta Node.js.

---

## Opción 2: Desde la terminal, dentro de `frontend`

1. Abre una terminal (PowerShell o CMD).
2. Ve a la carpeta **frontend** del proyecto. Por ejemplo:
   ```text
   cd C:\Users\TIC\gestor_lockers\frontend
   ```
   (Ajusta la ruta si tu proyecto está en otro sitio.)

3. Instala dependencias:
   ```text
   npm install
   ```

4. Genera el build:
   ```text
   npm run build
   ```

### Cómo abrir la terminal ya dentro de `frontend` (Cursor / VS Code)

- En el explorador de archivos del editor, clic derecho en la carpeta **frontend**.
- Elige **"Abrir en terminal integrada"** (o "Open in Integrated Terminal").
- En esa terminal ya estarás en `frontend`; ejecuta `npm install` y luego `npm run build`.

---

## Resultado

Tras un build correcto, se crea la carpeta **app/static/dashboard/** con los archivos que Flask usa. Arranca la app con `python run.py`, inicia sesión y entra a **/dashboard** para ver el dashboard React.
