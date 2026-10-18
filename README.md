# Didacteca · Prueba técnica AI Engineer Jr

Servicio en FastAPI que recibe una solicitud estructurada, recupera el contenido de una sección de un libro desde el Context Service y usa OpenAI para generar un **chat**, un **quiz** o una **actividad educativa**, siempre basados únicamente en ese contenido.

## Alcance entregado

| Capacidad | Estado |
|---|---|
| `chat` | Implementada |
| `quiz` | Implementada |
| `activity` | Implementada |

- **Tiempo aproximado dedicado:** [3 horas].
- **Versión a evaluar:** [tag `v1.0`].
- Las tres capacidades comparten un mismo flujo; solo cambian el prompt y el esquema de salida.

## Requisitos

- Python 3.12
- Acceso al Context Service y una credencial de OpenAI (entregadas por Didacteca)

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

En Linux o macOS: `source .venv/bin/activate`.

## Configuración

Copia el archivo de ejemplo y completa la clave:

```powershell
Copy-Item .env.example .env
```

| Variable | Descripción | Valor de ejemplo |
|---|---|---|
| `PROVIDED_SERVICE_BASE_URL` | URL base del Context Service | `https://temp.didacteca.site` |
| `OPENAI_API_KEY` | Credencial de OpenAI (no se sube al repo) | `pon_tu_clave_aqui` |
| `OPENAI_MODEL` | Modelo a usar | `gpt-4.1-mini` |

El valor es solo la clave, sin comillas ni repetir el nombre de la variable. `.env` está en `.gitignore`.

> El Context Service redirige `http` a `https` con un 301. Se configura `https` directamente porque un 301 sobre un POST puede convertirse en GET y fallar.

## Ejecución

```powershell
uvicorn src.main:app --reload
```

La API queda en `http://127.0.0.1:8000`. La documentación interactiva está en `http://127.0.0.1:8000/docs`.

## Ejemplos

Los ejemplos usan `curl` con comillas simples (Linux, macOS o Git Bash). En PowerShell conviene usar la documentación interactiva en `/docs` o el script `scripts/smoke_test.py`.

**Chat**

```bash
curl -X POST http://127.0.0.1:8000/execute -H "Content-Type: application/json" \
  -d '{"action":"chat","book_id":"book_001","section_id":"section_04","instructions":"¿Qué es el discriminante?"}'
```

```json
{"action": "chat", "answer": "El discriminante es la expresión Δ = b² − 4ac ..."}
```

**Quiz**

```bash
curl -X POST http://127.0.0.1:8000/execute -H "Content-Type: application/json" \
  -d '{"action":"quiz","book_id":"book_001","section_id":"section_04","instructions":"Genera un quiz de 3 preguntas de dificultad intermedia."}'
```

**Activity**

```bash
curl -X POST http://127.0.0.1:8000/execute -H "Content-Type: application/json" \
  -d '{"action":"activity","book_id":"book_001","section_id":"section_04","instructions":"Crea una actividad para realizar en equipos."}'
```

Como el usuario no indicó la duración, la respuesta incluye `"assumptions": ["Duración estimada de 20 minutos elegida por el sistema."]`.

**Caso problemático: pregunta que el libro no responde**

```bash
curl -X POST http://127.0.0.1:8000/execute -H "Content-Type: application/json" \
  -d '{"action":"chat","book_id":"book_001","section_id":"section_04","instructions":"¿Quién descubrió América?"}'
```

```json
{"status": "error", "code": "CONTENT_INSUFFICIENT", "message": "El contenido proporcionado solo trata sobre ecuaciones cuadráticas ...", "missing_fields": [], "details": {}}
```
(HTTP 422)

**Caso problemático: instrucciones contradictorias**

```bash
curl -X POST http://127.0.0.1:8000/execute -H "Content-Type: application/json" \
  -d '{"action":"quiz","book_id":"book_001","section_id":"section_04","instructions":"Un quiz de 3 preguntas y también de 10 preguntas."}'
```

```json
{"status": "needs_clarification", "code": "AMBIGUOUS_INSTRUCTIONS", "message": "Las instrucciones se contradicen: pides cantidades distintas de preguntas: 3, 10. Envía una versión con un solo valor.", "missing_fields": [], "details": {"conflicts": ["pides cantidades distintas de preguntas: 3, 10"]}}
```
(HTTP 422)

## Formato de respuestas

**Éxito:** HTTP 200 con el esquema del enunciado (`chat`, `quiz` o `activity`). Se añade un campo opcional `assumptions` cuando el sistema aplicó valores por defecto.

**No exitosas:** siempre llevan `status`, `code`, `message`, `missing_fields` y `details`. Un cliente distingue éxito de no-éxito por la presencia de `status`, sin interpretar texto libre.

| `status` | Significado |
|---|---|
| `error` | No se pudo completar la operación |
| `needs_clarification` | Falta información o hay contradicciones; el usuario debe enviar una solicitud corregida |
| `partial` | Se resolvió solo una parte; el recurso parcial viene en `details.resource` |

| `code` | HTTP | Cuándo |
|---|---|---|
| `MISSING_FIELDS` | 422 | Falta `action`, `book_id`, `section_id` o (en chat) la pregunta; `missing_fields` los lista |
| `UNSUPPORTED_ACTION` | 400 | `action` no es chat, quiz ni activity |
| `INVALID_REQUEST` | 422 | JSON con tipos incorrectos |
| `AMBIGUOUS_INSTRUCTIONS` | 422 | Instrucciones contradictorias |
| `BOOK_NOT_FOUND` / `SECTION_NOT_FOUND` | 404 | El Context Service no encuentra el libro o la sección |
| `CONTENT_INSUFFICIENT` | 422 | Sección vacía, o el contenido no permite cumplir la solicitud |
| `PARTIAL_RESULT` | 200 | Resultado parcial (`status: partial`) |
| `CONTEXT_SERVICE_ERROR` | 502 | Timeout, conexión, 5xx o respuesta inválida del Context Service |
| `LLM_ERROR` | 502 | Falla del servicio de IA (timeout, conexión, error de API) |
| `INVALID_MODEL_OUTPUT` | 502 | La salida del modelo no cumple el esquema tras un reintento |
| `INTERNAL_ERROR` | 500 | Error inesperado (el detalle va al log, no al usuario) |

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas no usan red ni OpenAI: el Context Service se simula con `respx` y el modelo con un reemplazo que devuelve respuestas predefinidas.

- `tests/test_api.py`: validación de solicitudes, éxitos, casos problemáticos, reintento y rechazo de salidas inválidas, error inesperado.
- `tests/test_context_client.py`: 404, timeout, 5xx, respuesta inválida, sección vacía.
- `tests/test_unit.py`: detección de contradicciones y protección de las etiquetas del prompt.

`scripts/smoke_test.py` lanza 10 solicitudes reales contra el servidor local (requiere servidor activo y credencial válida) para revisar el comportamiento de extremo a extremo.

## Arquitectura

```
POST /execute
   │
   ▼
main.py ── validate_request ── (acción, campos, contradicciones)
   │
   ▼
context_client.py ── Context Service (HTTP)
   │
   ▼
generator.py ── prompts.py ── llm_client.py ── OpenAI
   │              (validación Pydantic, reintento, supuestos)
   ▼
Respuesta de éxito o ErrorResponse
```

| Archivo | Responsabilidad |
|---|---|
| `src/main.py` | Endpoint, validación de entrada y manejo central de errores |
| `src/schemas.py` | Contratos de entrada y salida (Pydantic) |
| `src/context_client.py` | Cliente del Context Service; traduce cada fallo a un error propio |
| `src/llm_client.py` | Único punto de contacto con OpenAI |
| `src/prompts.py` | Construcción de los prompts |
| `src/generator.py` | Orquesta la generación, valida la salida y concilia supuestos |
| `src/conflicts.py` | Detección de contradicciones en las instrucciones |
| `src/errors.py` | `AppError`, la excepción controlada de la aplicación |
| `src/config.py` | Lectura de variables de entorno |

## Decisiones técnicas

- **Una sola llamada al modelo por solicitud.** El modelo devuelve un "sobre" con `status` (`ok`, `partial`, `insufficient_content`, `conflicting_instructions`), `reason` y el recurso. Así puede avisar que el contenido no alcanza en lugar de inventar.
- **SDK oficial de OpenAI**, modo JSON y temperatura 0.2 para respuestas fieles al texto.
- **Validación estricta de la salida con Pydantic** (4 opciones distintas, `correct_answer` entre ellas, campos no vacíos) y un reintento que le indica al modelo qué falló. Si vuelve a fallar, no se presenta como éxito.
- **El contenido del libro es dato, no instrucción.** Va entre etiquetas, el prompt del sistema lo declara así y se eliminan las etiquetas de cierre que aparezcan dentro del texto. Además, `action` siempre viene de la solicitud y la salida se valida contra el esquema de esa acción, así que un modelo manipulado no puede devolver otro formato como éxito.
- **El código decide lo que no debe depender del modelo:** los supuestos por defecto se concilian en código, las contradicciones numéricas se detectan antes de llamar a ningún servicio y las opciones del quiz se barajan para que la respuesta correcta no sea siempre la primera.
- **Los errores se modelan con una sola excepción** (`AppError`) y un manejador central.
- **Validación antes de la red:** acción, campos faltantes y contradicciones se revisan antes de consultar el Context Service o el modelo.
- **Una sección vacía no llega al modelo.**

## Supuestos

- Los libros y las instrucciones están en español.
- Valores por defecto: quiz de 5 preguntas con dificultad intermedia, actividad de 20 minutos. Siempre se informan en `assumptions`.
- En `chat`, `instructions` es la pregunta y es obligatoria.
- Cada solicitud es independiente: no hay estado ni conversación.

## Limitaciones conocidas

- **La detección de supuestos y contradicciones usa expresiones regulares** que solo entienden dígitos y español ("3 preguntas", sí; "tres preguntas", no). Un número cualquiera en un quiz cuenta como si el usuario hubiera dado la cantidad.
- **Que el contenido es insuficiente lo decide el modelo.** Puede equivocarse en ambos sentidos: rechazar algo respondible o responder algo con apoyo débil.
- **No se verifica que cada afirmación esté respaldada por el texto.** Un quiz o una explicación podría incluir información externa sin que el sistema lo detecte.
- Secciones muy largas no se dividen; podrían exceder la ventana de contexto del modelo.
- Con secciones cortas, un quiz largo puede repetir preguntas; el modelo suele devolver un resultado parcial.
- Un resultado parcial responde HTTP 200 con `status: partial`; un cliente descuidado podría tratarlo como éxito.
- Sin autenticación, límites de uso, caché ni reintentos con espera hacia el Context Service.
- Las pruebas automatizadas no validan la calidad real de las respuestas del modelo.

## Pendientes y mejoras

- Verificación de respaldo: una segunda pasada que compruebe que cada respuesta o explicación cita fragmentos del texto.
- Un conjunto de evaluación con solicitudes y resultados esperados.
- Salida estructurada con `json_schema` del proveedor.
- Registro estructurado, métricas, reintentos con espera y caché del contexto.
- Fragmentación para secciones largas y soporte de varias secciones.
- Detección de idioma y de números escritos con letras.

## Documento de decisiones

**1. ¿Cómo dividí el problema?**
En cuatro responsabilidades: validar la solicitud, obtener el contenido (Context Service), generar con el modelo, y validar y presentar la salida. Cada una vive en un módulo y las tres capacidades comparten el mismo flujo.

**2. ¿Por qué esta arquitectura?**
Porque el enunciado pide algo simple y justificable. Una llamada al modelo por solicitud, módulos pequeños con una sola función y sin frameworks de IA. Lo que no debe depender del modelo (contradicciones, supuestos, formato de errores, barajado) lo resuelve el código.

**3. ¿Qué situaciones consideré problemáticas?**
Datos faltantes, acción no soportada, libro o sección inexistentes, sección vacía, preguntas que el libro no responde, instrucciones contradictorias, peticiones que exceden el contenido (resultado parcial), intentos de inyección de instrucciones, salidas inválidas del modelo y fallas de los servicios externos. En ninguno el sistema se limita a generar una respuesta.

**4. ¿Qué limitaciones tiene?**
Las de la sección anterior. Las más importantes: no verifica que lo generado esté respaldado por el texto y depende del modelo para decidir si el contenido basta.

**5. ¿Qué mejoraría con más tiempo?**
Primero la verificación de respaldo y el conjunto de evaluación; después observabilidad, caché, reintentos y manejo de secciones largas.

**6. ¿Cómo evaluaría si funciona correctamente?**
- **Pruebas automatizadas** de la lógica determinista (como las que hay) en integración continua.
- **Conjunto de oro:** solicitudes con resultado esperado (éxito, rechazo, aclaración) para medir la tasa de acierto en cada caso.
- **Fidelidad al contenido:** revisión humana y un evaluador automático sobre una muestra, midiendo qué porcentaje de afirmaciones tiene respaldo en el texto.
- **Calidad del quiz:** que la respuesta correcta sea inequívoca y los distractores plausibles.
- **Robustez:** un banco de intentos de inyección.
- **Operación:** tasa de salidas inválidas y de reintentos, latencia, costo por solicitud y errores por tipo.