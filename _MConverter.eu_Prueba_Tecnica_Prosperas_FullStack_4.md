<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>PRUEBA TÉCNICA — FULL-STACK DEVELOPER</strong></p>
<p>Sistema de Procesamiento Asíncrono de Reportes</p>
<p><em>Prosperas · Proceso de Selección 2025</em></p></td>
</tr>
</tbody>
</table>

|                |           |                         |             |
|----------------|-----------|-------------------------|-------------|
| **⏱ 1 Semana** | **☁ AWS** | **🐍 Python / FastAPI** | **⚛ React** |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Stack requerido:</strong> Python 3.11+ · FastAPI · React 18+ · AWS (servicios a elección del candidato)</p>
<p><strong>Tiempo límite:</strong> 7 días calendario desde la recepción de este documento</p>
<p><strong>Entrega:</strong> Repositorio Git en GitHub — enlace enviado por email</p>
<p><strong>Modalidad:</strong> Take-home — individual, sin restricción de referencias técnicas</p>
<p><strong>Nivel evaluado:</strong> Semi-senior (core obligatorio) + Senior (retos bonus opcionales)</p></td>
</tr>
</tbody>
</table>

|        |                          |
|--------|--------------------------|
| **01** | **Contexto del Negocio** |

Una plataforma SaaS de analítica necesita un sistema que permita a sus usuarios generar **reportes de datos bajo demanda**. Dado que los reportes pueden tardar entre 5 segundos y varios minutos (según el volumen de datos), el procesamiento **no puede ser síncrono**. Tu tarea es construir la infraestructura completa --- backend, cola de mensajes, workers concurrentes y frontend --- que resuelva este problema.

El sistema debe manejar múltiples usuarios enviando solicitudes simultáneamente sin que se bloqueen entre sí, con visibilidad de estado en tiempo real y resiliencia ante fallos parciales.

|        |                            |
|--------|----------------------------|
| **02** | **Requisitos del Sistema** |

El sistema debe cumplir los siguientes comportamientos. **La elección de servicios AWS queda completamente a tu criterio** --- parte de la evaluación es analizar qué decidiste usar y por qué.

|                                   |                                                                                                                                                                                                               |
|-----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Requisito**                     | **Comportamiento esperado**                                                                                                                                                                                   |
| **1. Solicitud de reporte**       | El usuario completa un formulario en el frontend y envía la solicitud. El sistema debe responder de inmediato con un identificador de job y el estado inicial, sin bloquear al usuario mientras se procesa.   |
| **2. Desacoplamiento asíncrono**  | La solicitud debe encolarse en un servicio de mensajería de AWS para ser procesada de forma asíncrona. El componente que recibe la solicitud y el que la procesa deben estar desacoplados.                    |
| **3. Procesamiento concurrente**  | Uno o varios workers deben consumir trabajos de la cola de forma concurrente --- al menos dos solicitudes procesándose en paralelo. El procesamiento puede simularse (sleep aleatorio 5--30 s + datos dummy). |
| **4. Persistencia de estado**     | El estado de cada job (PENDING → PROCESSING → COMPLETED / FAILED) y su resultado deben persistirse en un servicio de base de datos de AWS.                                                                    |
| **5. Resiliencia ante fallos**    | Si el procesamiento de un job falla, el sistema debe tener una estrategia para manejarlo sin perder el mensaje ni bloquear los demás trabajos.                                                                |
| **6. Visibilidad en tiempo real** | El frontend debe reflejar los cambios de estado sin que el usuario recargue la página. La estrategia de actualización queda a tu criterio.                                                                    |

|                                                                                                                                                                                    |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Nota:** El \'procesamiento del reporte\' puede simularse con un sleep de duración aleatoria y generación de datos dummy. No se requiere integración con fuentes de datos reales. |

|        |                                      |
|--------|--------------------------------------|
| **03** | **Requisitos Core --- Obligatorios** |

### 3.1 Backend --- Python + FastAPI {#backend-python-fastapi}

- POST /jobs --- crea un nuevo job de reporte; devuelve { job_id, status: \'PENDING\' }

- GET /jobs/{job_id} --- devuelve estado actual y resultado (si completado)

- GET /jobs --- lista todos los jobs del usuario autenticado (paginado, min. 20 por página)

- Autenticación básica con JWT (sin OAuth externo requerido)

- Validación de payloads con Pydantic v2

- Manejo centralizado de errores (handlers globales, no try/except dispersos)

- Dockerfile funcional para despliegue en AWS

### 3.2 Cola de Mensajes y Workers --- AWS {#cola-de-mensajes-y-workers-aws}

- Al crear un job, la API debe publicar un mensaje a un servicio de colas de AWS (elección tuya)

- Uno o varios workers deben consumir esos mensajes y procesar los jobs de forma asíncrona

- El worker debe actualizar el estado del job en la base de datos a medida que avanza: PROCESSING → COMPLETED o FAILED

- El sistema debe procesar al menos 2 mensajes en paralelo --- sin que uno bloquee al otro

- Debe existir una estrategia para manejar mensajes que fallan repetidamente, sin que bloqueen la cola

### 3.3 Persistencia --- AWS {#persistencia-aws}

- Usar un servicio de base de datos de AWS (elección tuya) para persistir el estado de cada job

- Modelo de datos mínimo: job_id, user_id, status, report_type, created_at, updated_at, result_url

- Las consultas para listar jobs por usuario deben ser eficientes

- Script o instrucción para inicializar el esquema desde cero

### 3.4 Frontend --- React {#frontend-react}

- Formulario para solicitar un reporte (campos: report_type, date_range, format)

- Lista de jobs con estado visual (badge de colores: PENDING / PROCESSING / COMPLETED / FAILED)

- El estado debe actualizarse automáticamente --- sin que el usuario recargue la página

- Manejo de errores con feedback visual al usuario (no alert() nativo)

- Diseño responsive --- debe verse bien en móvil y desktop

### 3.5 Infraestructura --- LocalStack en desarrollo, AWS real en producción {#infraestructura-localstack-en-desarrollo-aws-real-en-producción}

El sistema tiene dos ambientes claramente separados:

- Desarrollo local: usar LocalStack para emular los servicios de AWS. El entorno completo debe levantarse con docker compose up sin ninguna configuración adicional

- Producción: la aplicación debe desplegarse en una cuenta AWS real y quedar accesible desde internet mediante una URL pública

- Variables de entorno manejadas con .env.example --- nunca hardcodear credenciales ni secretos en el repositorio

- El README debe incluir instrucciones claras para ambos ambientes: cómo levantar localmente y cómo se hace el despliegue a producción

|         |                                    |
|---------|------------------------------------|
| **3.6** | **Pipeline CI/CD --- Obligatorio** |

El repositorio debe incluir un pipeline de CI/CD funcional con **GitHub Actions** que, al hacer push a la rama principal, **despliega automáticamente la aplicación a producción en AWS**.

El objetivo es ver la aplicación viva en una URL pública real --- no en local, no en LocalStack. El pipeline es el mecanismo que lleva el código desde el repositorio hasta ese estado. Qué stages incluye, qué herramientas usa y cómo estructura ese proceso **queda completamente a tu criterio**. Documenta en el README por qué lo diseñaste así.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Lo que se evaluará:</strong> Que el pipeline realmente despliegue a AWS, las decisiones detrás del diseño del pipeline, y la coherencia con el sistema construido</p>
<p><strong>Badge:</strong> El README debe mostrar el badge de GitHub Actions en verde y la URL pública de la aplicación en producción</p></td>
</tr>
</tbody>
</table>

|         |                                                      |
|---------|------------------------------------------------------|
| **3.7** | **Documentación Técnica y AI Skill --- Obligatorio** |

El repositorio debe incluir dos artefactos de documentación. **Ambos deben generarse usando una herramienta de IA** --- Claude Code, Cursor, Windsurf, GitHub Copilot u otra herramienta de vibe coding o copiloto. No se acepta documentación escrita a mano sin evidencia de uso de IA.

Este requisito evalúa dos cosas en paralelo: la capacidad de comunicar decisiones técnicas con claridad, y la habilidad de **usar herramientas de IA de forma efectiva y profesional** --- saber prompt-ear bien, revisar el output, corregir lo que la IA no entiende y producir un resultado que realmente sirva. Eso es exactamente lo que se espera en el trabajo diario.

|                                                                                                                                                                                                                                                                                                  |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Evidencia de uso de IA requerida:** En el README o en un archivo AI_WORKFLOW.md debe quedar constancia de qué herramienta se usó y cómo: qué prompts se dieron, qué se tuvo que corregir, qué limitaciones encontró. No es necesario que sea extenso --- con un párrafo honesto es suficiente. |

### Artefacto 1 --- TECHNICAL_DOCS.md {#artefacto-1-technical_docs.md}

Generado con IA a partir del código del proyecto. Debe documentar el sistema de forma completa --- útil para un desarrollador nuevo que nunca lo vio. Contenido mínimo esperado:

- Diagrama de arquitectura (ASCII art o Mermaid) con todos los componentes y el flujo de datos

- Tabla de servicios AWS utilizados: qué servicio, para qué, y por qué se eligió sobre alternativas

- Decisiones de diseño relevantes: trade-offs considerados y alternativas descartadas

- Guía de setup local: pasos exactos para levantar el entorno con LocalStack desde cero

- Guía de despliegue: cómo funciona el pipeline y qué hace cada step

- Variables de entorno: descripción de cada variable del .env.example

- Instrucciones para ejecutar los tests y qué cubre cada suite

### Artefacto 2 --- SKILL.md {#artefacto-2-skill.md}

Un archivo diseñado específicamente para ser inyectado como contexto en un agente de IA al trabajar con este proyecto. La IA que lo lea debe poder operar sobre el código sin necesidad de leer cada archivo. Debe incluir como mínimo:

- Descripción del sistema: qué hace, cómo funciona, qué problema resuelve

- Mapa del repositorio: qué hay en cada carpeta y para qué sirve cada módulo

- Patrones del proyecto: cómo agregar una nueva ruta, cómo publicar a la cola, cómo leer el estado de un job

- Comandos frecuentes: levantar local, correr tests, hacer deploy manual, ver logs

- Errores comunes y cómo resolverlos

- Sección \'cómo extender\': instrucciones paso a paso para agregar un nuevo tipo de reporte

**Test en vivo del SKILL.md:** En la entrevista de defensa, el evaluador abrirá una sesión de Claude (u otra herramienta) con el SKILL.md como **único contexto** --- sin acceso al código --- y hará preguntas sobre el proyecto. Por ejemplo:

- ¿Cómo funciona el worker? ¿Qué pasa si falla el procesamiento de un mensaje?

- ¿Qué servicio de AWS se usa para la cola y por qué se eligió?

- ¿Cómo agrego un nuevo tipo de reporte al sistema?

- ¿Cómo levanto el entorno local desde cero?

- ¿Qué hace exactamente el endpoint POST /jobs?

Si el agente puede responder todas las preguntas con precisión usando solo el SKILL.md, la documentación está bien hecha. Si se inventa respuestas, dice \'no tengo esa información\' o da respuestas vagas, **el SKILL.md está incompleto.**

|        |                                               |
|--------|-----------------------------------------------|
| **04** | **Retos Bonus --- Nivel Senior (opcionales)** |

Los siguientes retos son **completamente opcionales**. Resolverlos suma puntos y diferencia candidatos senior de semi-senior. No penaliza no hacerlos.

|                                           |                                                                                                                                                                                                                |
|-------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Reto**                                  | **Descripción**                                                                                                                                                                                                |
| **B1 --- Prioridad de mensajes**          | Implementa dos colas o canales de prioridad (alta y estándar) y una lógica de enrutamiento en la API según el tipo de reporte. El worker debe preferir los trabajos de alta prioridad.                         |
| **B2 --- Circuit Breaker**                | Implementa el patrón Circuit Breaker en el worker: si el procesamiento falla N veces consecutivas, el worker entra en estado \'open\' y deja de intentar procesar ese tipo de reporte por un período definido. |
| **B3 --- Notificaciones en tiempo real**  | Reemplaza el polling del frontend por una estrategia push (WebSockets u otro mecanismo). El servidor debe notificar proactivamente cuando el estado de un job cambia.                                          |
| **B4 --- Retry con back-off exponencial** | Implementa back-off exponencial en el worker antes de reintentar un mensaje fallido, en lugar de reintentar de inmediato.                                                                                      |
| **B5 --- Observabilidad**                 | Agrega structured logging, métricas de negocio enviadas a un servicio de monitoreo de AWS, y un endpoint GET /health que reporte el estado de cada dependencia del sistema.                                    |
| **B6 --- Tests avanzados**                | Cobertura \>= 70% en el backend con pytest. Incluye unit tests del worker, integration tests del endpoint POST /jobs, y al menos un test que simule un fallo de procesamiento.                                 |

|        |                           |
|--------|---------------------------|
| **05** | **Rúbrica de Evaluación** |

|                                       |             |                                                                                     |
|---------------------------------------|-------------|-------------------------------------------------------------------------------------|
| **Criterio**                          | **Puntos**  | **Indicadores clave**                                                               |
| **Arquitectura & Diseño AWS**         | **10 pts**  | Decisión de servicios justificada, separación de responsabilidades, flujo coherente |
| **Manejo de Colas & Mensajería**      | **15 pts**  | Cola desacoplada, manejo de fallos, mensajes concurrentes, estrategia de reintentos |
| **Concurrencia & Workers**            | **15 pts**  | \>=2 workers en paralelo, sin race conditions, estado consistente en BD             |
| **API REST (FastAPI)**                | **10 pts**  | Endpoints correctos, validación Pydantic, manejo de errores, JWT                    |
| **Frontend (React)**                  | **10 pts**  | UX funcional, actualización de estado, responsive, sin errores en consola           |
| **Despliegue en producción AWS**      | **15 pts**  | URL pública accesible, servicios AWS reales corriendo, HTTPS                        |
| **Pipeline CI/CD**                    | **10 pts**  | Deploy automático a AWS al hacer push, badge verde, decisiones documentadas         |
| **Documentación (TECHNICAL_DOCS.md)** | **10 pts**  | Completa, clara, útil para un dev nuevo; diagrama de arquitectura presente          |
| **AI Skill (SKILL.md)**               | **5 pts**   | Permite a un agente entender y operar sobre el proyecto sin leer el código          |
| **Bonus (máx. extra)**                | **+25 pts** | Puntos adicionales por retos B1--B6 completados y bien implementados                |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Puntaje mínimo aprobatorio:</strong> 60 / 100 puntos (sin contar bonus)</p>
<p><strong>Puntaje para avanzar a entrevista técnica:</strong> 70+ puntos o 80+ con bonus</p></td>
</tr>
</tbody>
</table>

|        |                                             |
|--------|---------------------------------------------|
| **06** | **Criterios de Descalificación Automática** |

Los siguientes errores resultan en descalificación inmediata, independiente del puntaje obtenido:

- Credenciales AWS, tokens JWT o passwords commiteados en el repositorio

- El sistema no arranca localmente con docker compose up siguiendo el README

- La aplicación no está desplegada en AWS real con URL pública accesible al momento de la entrega

- No existe pipeline de GitHub Actions o nunca corrió (sin historial de ejecuciones en el repo)

- No se usa ningún servicio de mensajería/colas de AWS (el procesamiento asíncrono es el núcleo del challenge)

- El worker es completamente síncrono (sin ningún tipo de concurrencia)

- No se crea el usuario IAM de acceso para revisión (ver sección de entrega)

- Ausencia de TECHNICAL_DOCS.md o SKILL.md en el repositorio

- Evidencia de código generado íntegramente por IA sin comprensión del candidato (se verifica en la entrevista técnica de revisión)

|        |                                        |
|--------|----------------------------------------|
| **07** | **Estructura de Repositorio Sugerida** |

Organización recomendada (puedes adaptarla):

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>tu-nombre-prosperas-challenge/</strong></p>
<p>backend/ # FastAPI app + worker</p>
<p>app/</p>
<p>api/ # routers FastAPI</p>
<p>core/ # config, auth, db</p>
<p>models/ # Pydantic + ORM models</p>
<p>services/ # business logic</p>
<p>worker/ # queue consumer + processor</p>
<p>Dockerfile</p>
<p>frontend/ # React app</p>
<p>src/</p>
<p>components/ # UI components</p>
<p>hooks/ # custom hooks</p>
<p>services/ # API calls</p>
<p>local/ # docker-compose + LocalStack (desarrollo)</p>
<p>infra/ # IaC para producción en AWS</p>
<p>.github/workflows/ # GitHub Actions pipeline</p>
<p>.env.example # variables de entorno</p>
<p><strong>TECHNICAL_DOCS.md # documentación técnica completa</strong></p>
<p><strong>SKILL.md # contexto para agentes de IA</strong></p>
<p>README.md # setup local + URL de producción</p></td>
</tr>
</tbody>
</table>

|        |                                   |
|--------|-----------------------------------|
| **08** | **Proceso de Entrega y Revisión** |

|                            |                                                                                                                                                                                                                                                      |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Paso**                   | **Descripción**                                                                                                                                                                                                                                      |
| **Paso 1 --- Repo**        | Crea un repositorio público en GitHub con el nombre: {tu-nombre}-prosperas-challenge                                                                                                                                                                 |
| **Paso 2 --- Despliegue**  | Despliega la aplicación en tu cuenta personal de AWS. El sistema debe estar corriendo y accesible desde internet al momento de la entrega.                                                                                                           |
| **Paso 3 --- Usuario IAM** | Crea un usuario IAM en tu cuenta AWS con permisos de AdministratorAccess y comparte las credenciales de acceso (Access Key ID + Secret Access Key) de forma segura junto con tu entrega. Esto permite revisar cómo implementaste la infraestructura. |
| **Paso 4 --- README**      | El README debe incluir: URL pública de la aplicación en producción, diagrama de arquitectura, pasos para correr localmente con LocalStack, y decisiones de diseño.                                                                                   |
| **Paso 5 --- Entrega**     | Envía el enlace al repo + URL de producción + credenciales IAM al correo del reclutador. Asunto: \[Prosperas\] Prueba Técnica --- {Tu Nombre}.                                                                                                       |
| **Paso 6 --- Defensa**     | Se revisará el código, la infraestructura en la consola AWS y se pedirá explicar decisiones de diseño y extender una funcionalidad en vivo (30 min).                                                                                                 |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Costos AWS:</strong> La prueba está diseñada para correr dentro del free tier de AWS. Si llegas a generar algún costo, Prosperas lo reembolsa hasta un máximo de USD $10.</p>
<p><strong>Seguridad de credenciales:</strong> El usuario IAM es solo para revisión de la prueba. Una vez finalizado el proceso, elimínalo de tu cuenta.</p></td>
</tr>
</tbody>
</table>

|        |                          |
|--------|--------------------------|
| **09** | **Preguntas Frecuentes** |

|                                              |                                                                                                                                                                                  |
|----------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Pregunta**                                 | **Respuesta**                                                                                                                                                                    |
| **¿Necesito una cuenta AWS real?**           | Sí. La aplicación debe desplegarse en AWS real y quedar accesible desde internet. Para desarrollo local puedes usar LocalStack, pero la entrega final es una URL pública en AWS. |
| **¿Cuánto me puede costar?**                 | La prueba está diseñada para mantenerse dentro del free tier de AWS. En el peor caso, el costo es menor a \$10 USD --- y Prosperas lo cubre si llegas a ese límite.              |
| **¿Puedo usar otros frameworks de React?**   | Sí: Next.js, Vite+React o CRA. Lo importante es que sea React, no Angular o Vue.                                                                                                 |
| **¿Qué servicios de AWS debo usar?**         | Esa decisión es tuya --- es parte de la evaluación. Elige los que consideres más adecuados, despliégalos y documenta el porqué en tu README.                                     |
| **¿Puedo usar librerías de terceros?**       | Sí, sin restricciones razonables. Evita librerías que resuelvan completamente la concurrencia de forma opaca sin que puedas explicar cómo funcionan por dentro.                  |
| **¿Se penaliza usar IA (Copilot, ChatGPT)?** | No se penaliza usar IA como asistente. Se penaliza no entender el código generado. Prepárate para explicar cada parte en la entrevista.                                          |

|        |                            |
|--------|----------------------------|
| **10** | **Recursos de Referencia** |

**Documentación oficial recomendada:**

- FastAPI --- https://fastapi.tiangolo.com

- Boto3 (SDK AWS para Python) --- https://boto3.amazonaws.com/v1/documentation/api/latest/index.html

- AWS Services Overview --- https://docs.aws.amazon.com

- LocalStack (emulador AWS local) --- https://docs.localstack.cloud

- Pydantic v2 --- https://docs.pydantic.dev/latest

- asyncio en Python --- https://docs.python.org/3/library/asyncio.html

|                                                                                                                                                                                                                                    |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Suerte:** Disfruta el proceso. Esta prueba refleja problemas reales con los que trabajamos a diario. Si tienes dudas sobre el enunciado, escríbenos --- preferimos aclarar que ver una implementación basada en un malentendido. |

*Prosperas · hiring@prosperas.co · prosperas.co*
