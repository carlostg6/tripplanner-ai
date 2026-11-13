# Guion de la demostración obligatoria (12 pasos)

**Escenario:** *"Quiero organizar unas vacaciones de cuatro días en Cartagena. Salgo desde Bogotá, viajo con dos personas más y tengo un presupuesto de 5 millones de pesos. Quiero conocer el clima, encontrar vuelos y organizar algunas actividades turísticas."*

Antes de empezar, deja abiertas tres pestañas:

- la app (`FrontendUrl`);
- la consola de **DynamoDB → Explore items** de `tripplanner-data`;
- **CloudWatch Logs** del runtime de AgentCore.

| # | Acción en vivo | Qué mostrar / evidencia |
|---|---|---|
| 1 | Abrir la `FrontendUrl` e iniciar sesión | Login de Cognito y Dashboard vacío. |
| 2 | Clic en **Planear con el asistente** (o pegar el prompt en *Asistente*) | El texto llega token a token (HTTP streaming). |
| 3 | El Orchestrator interpreta la solicitud | Indicadores "Orchestrator · Delegando… al Flight Agent / Weather Agent". El agente propone fechas concretas e interpreta "dos personas más" como 3 viajeros. |
| 4 | Flight consulta vuelos vía MCP | Estado "Flight Agent · Consultando vuelos en el MCP de vuelos…". |
| 5 | Weather consulta el clima vía MCP | Estado "Weather Agent · Consultando el clima en el MCP de clima…". |
| 6 | El frontend presenta los resultados | **Tarjetas comparativas de vuelos** (ordenar por precio, duración o salida) y **tarjetas de clima por día**. Es la Agent-Driven UI. |
| 7 | Escribir: *"Crea el viaje con el vuelo más económico, genera el itinerario y registra la reserva"* | Estado "Tool CreateTrip · Guardando tu viaje…" y aparece la tarjeta del viaje. |
| 8 | Se genera el itinerario | Estado "Tool CreateItinerary" y aparece la **agenda por día** con horas, lugares y costos. |
| 9 | Se registra una reserva simulada | Estado "Tool CreateReservation" y aparece una reserva con la etiqueta **SIMULADA** y el código `SIM-XXXXXX`. |
| 10 | Mostrar DynamoDB | Ítems `TRIP#…`, `ITIN#…` y `RES#…` bajo `USER#<sub>`, con `createdBy = agent`. |
| 11 | Cerrar la app (**Salir** y cerrar la pestaña) | — |
| 12 | Volver a ingresar | El Dashboard muestra el viaje próximo y la reserva. En *Mis viajes* → detalle se ven el itinerario, el presupuesto comprometido y las reservas. En el *Asistente*, preguntar *"¿Qué viaje tenía planeado?"*: el agente recuerda la conversación (memoria) y consulta `get_trips` (persistencia). |

## Puntos extra para la sustentación (si sobra tiempo)

- **Canal 1 sin agente:** en *Reservas* → **Editar**, cambiar el estado a *Pendiente*. Intentar *Confirmada* sin proveedor real: la opción está deshabilitada y la API responde 409.
- **Validaciones:** crear un viaje con la fecha de regreso anterior a la salida y mostrar el error 400 con el detalle por campo.
- **Seguridad:** escribir en el chat *"guarda mi tarjeta 4111 1111 1111 1111"*. El agente se niega, y si intentara guardarla la Lambda respondería `PAYMENT_DATA_FORBIDDEN`.
- **Preferencias:** decir *"soy vegetariano y prefiero un ritmo relajado"*. Se ejecuta la Tool `save_preferences` y los cambios aparecen en *Preferencias*.
- **Aislamiento:** iniciar sesión con otro usuario y comprobar que no ve los viajes del primero.

## Si algo falla durante la demo

- **Error en el chat:** revisa CloudWatch del runtime. Los errores de las Tools vuelven al agente como `ok:false` y él los explica.
- **Lentitud del modelo:** el primer turno de una sesión nueva puede tardar más (*cold start* del contenedor y de los MCP). Haz una consulta de calentamiento antes de la presentación.
