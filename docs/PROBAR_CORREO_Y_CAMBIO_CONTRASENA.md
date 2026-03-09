# Cómo probar el correo y el aviso "Has cambiado tu contraseña"

## 1. Probar solo el envío del correo (rápido)

Para comprobar que el servidor de correo y el mensaje "Contraseña actualizada" funcionan **sin hacer el flujo completo**:

```powershell
cd C:\Users\TIC\gestor_lockers
python scripts/probar_correo.py tu-correo@ejemplo.com
```

- Sustituye `tu-correo@ejemplo.com` por un correo donde quieras recibir la prueba (por ejemplo tu correo personal o el de un usuario de la app).
- Si no pasas correo, se usa el de `MAIL_USERNAME` del `.env`.

Deberías recibir un correo con asunto **"Contraseña actualizada — LockerBeef"** y el texto de confirmación. Si no llega, revisa carpeta de spam y la configuración MAIL_* en `.env`.

---

## 2. Probar el flujo completo (restablecer + aviso por correo)

Así se ve todo el proceso de restablecer contraseña y que el usuario reciba el aviso.

### Paso 1: Usuario con correo real

- En la base de datos debe existir un usuario con un **email al que tengas acceso** (para recibir los dos correos).
- Si no, créalo desde Registro o en la BD y anota el email y la contraseña actual (para poder iniciar sesión después si quieres).

### Paso 2: Solicitar restablecer contraseña

1. Abre: `http://127.0.0.1:5000`
2. Clic en **"¿Olvidaste tu contraseña?"**
3. Escribe el **correo de ese usuario** y pulsa **"Enviar instrucciones"**.
4. Revisa ese correo: debe llegar el mensaje con el **enlace para restablecer contraseña**. (Si no llega, revisa spam y que MAIL_* en `.env` esté bien.)

### Paso 3: Cambiar la contraseña

1. En el correo, haz clic en el enlace (o cópialo en el navegador).
2. En la pantalla "Nueva contraseña", escribe la **nueva contraseña** dos veces y pulsa **"Guardar nueva contraseña"**.
3. Debe aparecer el mensaje: *"Contraseña actualizada correctamente. Ya puedes iniciar sesión. Revisa tu correo para la confirmación."*

### Paso 4: Comprobar el aviso "Has cambiado tu contraseña"

1. Revisa de nuevo la bandeja (y spam) del **mismo correo del usuario**.
2. Debe llegar un **segundo correo** con asunto **"Contraseña actualizada — LockerBeef"** y el texto que confirma que la contraseña fue cambiada.

Si recibes ese segundo correo, el aviso por correo está funcionando correctamente.

### Paso 5: (Opcional) Comprobar que la nueva contraseña sirve

1. Ve a la pantalla de login.
2. Inicia sesión con ese **email** y la **nueva contraseña** que acabas de poner.
3. Deberías entrar al dashboard sin problemas.

---

## Resumen

| Qué quieres comprobar | Cómo |
|------------------------|------|
| Que el servidor envía correos y el texto del aviso | `python scripts/probar_correo.py tu@correo.com` |
| Que todo el flujo (restablecer + aviso) funciona | Sigue la sección 2 (flujo completo) con un usuario cuyo correo puedas abrir |
