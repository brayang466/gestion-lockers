# Diseño de formularios: Registro de Personal, Ingreso de Lockers e Ingreso de Dotación

**Registro de Personal**, **Ingreso de Lockers** e **Ingreso de Dotación** son también pantallas de **registro en la app** (no solo importación desde CSV). Campos sugeridos para cada uno:

---

## REGISTRO DE PERSONAL (alta de personal desde la app)

Campos sugeridos para el formulario:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| ID Personal | texto | Identificador interno (opcional si se auto-genera). |
| Operario | texto, obligatorio | Nombre del operario/personal. |
| Identificación | texto | Documento (DNI, cédula, etc.). |
| Area | texto | Área o departamento. |
| Talla | texto | Talla de uniforme/EPP si aplica. |
| Area de Lockers | texto | Zona o sector de lockers asignable. |
| Estado | lista | Activo / Inactivo / Baja (u otros que uses). |
| Observaciones | texto largo | Notas opcionales. |

Al guardar, se inserta un registro en la tabla **registro_personal**.

---

## INGRESO DE LOCKERS (registro de nuevos lockers)

## INGRESO DE LOCKERS (registro de nuevos lockers)

Campos sugeridos para el formulario:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| Código de Lockers | texto, obligatorio | Identificador único del locker (ej. L-001). |
| Area | texto | Zona/área donde se ubica. |
| Area de Lockers | texto | Agrupación o sector de lockers. |
| Estado | lista | Disponible / Ocupado / Mantenimiento. |
| Unidad | texto | Unidad organizativa o sede. |
| Fecha de ingreso | fecha | Fecha en que se da de alta. |
| Observaciones | texto largo | Notas opcionales. |

Al guardar, se puede insertar también un registro en **BASE DE LOCKERS** (para que aparezca en el listado base) y opcionalmente en **LOCKER DISPONIBLES** si el estado es “disponible”.

---

## INGRESO DE DOTACION (registro de nuevas dotaciones)

Campos sugeridos para el formulario:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| Código de Dotación | texto, obligatorio | Identificador del tipo de dotación. |
| Cantidad | número | Unidades que se ingresan. |
| Area de uso | texto | Área donde se usará. |
| Talla | texto | Si aplica (ej. S, M, L, número). |
| Estado | lista | Disponible / Asignado / Baja. |
| Fecha de ingreso | fecha | Fecha del ingreso. |
| Observaciones | texto largo | Notas opcionales. |

Al guardar, se puede actualizar **DOTACIONES DISPONIBLES** (sumar cantidad) o **BASE DE DOTACIONES** (catálogo de tipos).

---

Cuando implementes login y dashboard, **Registro de Personal**, **Ingreso de Lockers** e **Ingreso de Dotación** serán pantallas de formulario dentro de sus respectivos módulos.
