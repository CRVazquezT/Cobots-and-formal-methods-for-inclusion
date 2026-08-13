**COBOT PARA INCLUSION:**

**celda robótica teleoperada**

**  
Versión: 7 agosto 2026**

**Subestación: Celda robot**

**Nombre de script: raspberry2.drl**

**Descripción: Programa DRL del controlador de robot Doosan**

# 1\. Objetivo

El presente documento describe el funcionamiento del programa DRL implementado en el robot Doosan, denomindo raspberrypi2, para establecer una comunicación TCP/IP bidireccional con una Raspberry Pi 5. La Raspberry Pi actúa como equipo externo de supervisión y control, mientras que el robot recibe comandos de movimiento y control del gripper y, simultáneamente, transmite información de su estado. El robot cuenta con gripper Onrobot que cuenta con un programa propio, el controlador del robot activa el cierre o apertura del gripper mediante una señal digital en el puerto DO\[8\].

# 2\. Arquitectura general del sistema

La comunicación se realiza mediante un socket TCP. El robot abre un socket en el puerto 20002 y mantiene un bucle principal de recepción. Una vez establecida la conexión, se crea además un hilo independiente denominado send_tcp_pos(), encargado de transmitir periódicamente la pose actual del robot a la Raspberry Pi.

| Componente     | Función                                                                           | Dirección     |
| -------------- | --------------------------------------------------------------------------------- | ------------- |
| Raspberry Pi 5 | Envía comandos de movimiento y control del gripper; recibe información del robot. | Bidireccional |
| Robot Doosan   | Recibe comandos, ejecuta movimientos, controla DO\[8\] y transmite su pose.       | Bidireccional |
| Socket TCP     | Canal de comunicación entre ambos equipos.                                        | TCP/IP        |
| Puerto         | Puerto utilizado por el socket del robot.                                         | 20002         |

Flujo conceptual:  
Raspberry Pi 5 → TCP/IP → Robot Doosan → procesamiento del comando → movimiento / DO\[8\]  
Robot Doosan → TCP/IP → Raspberry Pi 5 → actualización periódica de pose y estado

# 3\. Variables globales

| Variable  | Función                                     | Uso                                                                                     |
| --------- | ------------------------------------------- | --------------------------------------------------------------------------------------- |
| sock_id   | Identificador del socket TCP activo.        | Compartido por el bucle principal y el hilo de transmisión.                             |
| flag_hilo | Bandera de control del hilo de transmisión. | Mientras vale 1, send_tcp_pos() continúa enviando datos.                                |
| reg_DO8   | Registro software del estado de DO\[8\].    | Se actualiza al activar/desactivar el gripper y se incluye en la transmisión periódica. |

# 4\. Hilo de transmisión de la pose

La función send_tcp_pos() se ejecuta mediante thread_run() después de abrir correctamente el socket. Su objetivo es evitar que la transmisión periódica de información bloquee el bucle principal encargado de recibir y ejecutar comandos.

En cada iteración, el hilo obtiene la pose actual mediante get_current_posx(ref=DR_BASE). La información se formatea como siete campos separados por comas y termina con un salto de línea. El séptimo campo corresponde a reg_DO8.

Formato de transmisión periódica:

X,Y,Z,RX,RY,RZ,DO8\\n

El intervalo definido en el programa es de 0.5 s, por lo que el hilo intenta transmitir información aproximadamente dos veces por segundo.

# 5\. Bucle principal de recepción

El programa mantiene un while True que supervisa la conexión. Si existe un socket anterior, intenta cerrarlo, limpia sock_id y espera 0.5 s antes de intentar establecer nuevamente la conexión.

Cuando server_socket_open(20002) tiene éxito, se inicializa el arreglo dl con siete posiciones y se inicia el hilo send_tcp_pos(). A continuación, el bucle principal ejecuta server_socket_read(sock_id, timeout=1) para recibir comandos desde la Raspberry Pi.

# 6\. Protocolo de comandos recibido

El programa espera un mensaje compuesto por siete valores numéricos separados por comas. Los primeros seis valores representan un desplazamiento de posición/orientación y el séptimo valor, denominado vg, determina la acción asociada al mensaje.

| Campo        | Índice | Significado      | Tratamiento                                       |
| ------------ | ------ | ---------------- | ------------------------------------------------- |
| dl\[0\]      | 1      | Desplazamiento X | Parte del offset enviado a amovel().              |
| dl\[1\]      | 2      | Desplazamiento Y | Parte del offset enviado a amovel().              |
| dl\[2\]      | 3      | Desplazamiento Z | Parte del offset enviado a amovel().              |
| dl\[3\]      | 4      | Rotación RX      | Parte del offset enviado a amovel().              |
| dl\[4\]      | 5      | Rotación RY      | Parte del offset enviado a amovel().              |
| dl\[5\]      | 6      | Rotación RZ      | Parte del offset enviado a amovel().              |
| dl\[6\] / vg | 7      | Código de acción | Determina movimiento, gripper o consulta de pose. |

# 7\. Interpretación del parámetro vg

| Condición                     | Acción           | Resultado                                                                  |
| ----------------------------- | ---------------- | -------------------------------------------------------------------------- |
| vg <= 1.5                     | Movimiento       | Se ejecuta amovel() con los seis valores de offset.                        |
| vg > 0.5 dentro de vg <= 1.5  | DO\[8\] = 1      | Se activa la salida digital y reg_DO8 pasa a 1.                            |
| vg <= 0.5 dentro de vg <= 1.5 | DO\[8\] = 0      | Se desactiva la salida digital y reg_DO8 pasa a 0.                         |
| vg == 2.0                     | Consulta de pose | Se obtiene la pose actual y se transmite inmediatamente a la Raspberry Pi. |

Por tanto, el mismo mensaje de siete campos contiene tanto el desplazamiento solicitado como un valor de control que permite accionar el gripper o solicitar información de estado.

# 8\. Movimiento del robot

Cuando vg <= 1.5, el programa construye el vector offset con los seis primeros valores recibidos y ejecuta:

amovel(offset, v=200, a=200, mod=DR_MV_MOD_REL, ref=DR_BASE)

El movimiento se configura como relativo (DR_MV_MOD_REL) y utiliza DR_BASE como referencia. La velocidad y aceleración indicadas en el código son v=200 y a=200.

# 9\. Control del gripper mediante DO\[8\]

El gripper está conectado a la salida digital DO\[8\]. El programa utiliza tanto la salida física set_digital_output(8, ...) como la variable software reg_DO8 para mantener un registro del estado que se transmite periódicamente.

| Condición                   | DO\[8\] | reg_DO8 |
| --------------------------- | ------- | ------- |
| vg > 0.5 (cuando vg <= 1.5) | 1       | 1       |
| vg <= 0.5                   | 0       | 0       |

# 10\. Consulta y envío de pose bajo demanda

Cuando vg == 2.0, el programa no ejecuta un movimiento. En su lugar, obtiene la pose actual mediante get_current_posx() y genera un mensaje con X, Y, Z, RX, RY, RZ y un séptimo valor denominado dof. Ese mensaje se envía inmediatamente por el mismo socket.

mensaje="{},{},{},{},{},{},{}\\n".format(rd_x,rd_y,rd_z,rd_rx,rd_ry,rd_rz,dof)

Observación importante: en la versión transcrita, dof está fijado explícitamente a 1.0. Las líneas que consultarían directamente la salida digital están comentadas. Por ello, esta respuesta bajo demanda no representa necesariamente el estado real de DO\[8\].

# 11\. Gestión de desconexiones y errores

El programa incorpora varios mecanismos de recuperación. Si la lectura del socket devuelve res <= 0, el bucle de recepción se interrumpe. Posteriormente se cierra el socket, se limpia sock_id, se pone flag_hilo a 0 y se detiene el hilo mediante thread_stop(th_id).

En caso de excepción general, el programa intenta cerrar el socket, limpia sock_id y espera antes de volver a intentar la conexión. También existen bloques try/except internos para errores durante la captura de la pose y durante el procesamiento de los datos recibidos.

# 12\. Secuencia de operación

1. El robot entra en el bucle de gestión de conexión.
2. Se abre el socket TCP en el puerto 20002.
3. Se inicializa el arreglo de recepción de siete valores.
4. Se inicia el hilo send_tcp_pos().
5. El hilo transmite periódicamente la pose actual y reg_DO8.
6. El hilo principal espera mensajes de la Raspberry Pi.
7. El mensaje recibido se decodifica como UTF-8 y se separa mediante comas.
8. Si contiene siete valores, se convierten a float.
9. Los seis primeros valores se interpretan como offset y el séptimo como vg.
10. Según vg, el robot realiza un movimiento, cambia DO\[8\] o devuelve una pose bajo demanda.
11. Si la comunicación termina o se produce un error, se cierra el socket y se detiene el hilo.
12. El programa vuelve a intentar establecer la conexión.

# 13\. Resumen del protocolo

Comando Raspberry Pi → Robot:

X,Y,Z,RX,RY,RZ,VG\\n

Respuesta periódica Robot → Raspberry Pi:

X,Y,Z,RX,RY,RZ,DO8\\n

Respuesta bajo demanda cuando VG == 2.0:

X,Y,Z,RX,RY,RZ,DOF\\n

# 14\. Observaciones técnicas y puntos a validar

- El protocolo depende de siete valores separados por comas. La implementación actual no muestra un mecanismo explícito de acumulación de mensajes TCP; para una implementación robusta conviene validar el comportamiento ante segmentación o agrupación de paquetes.
- El valor vg tiene una doble función: selecciona la operación y, para valores <= 1.5, también interviene en la activación del gripper mediante el umbral 0.5.
- La pose periódica incluye reg_DO8, que es un estado software actualizado cuando el programa conmuta DO\[8\].
- La respuesta asociada a vg == 2.0 utiliza dof=1.0 fijo en la versión transcrita; debe validarse si la Raspberry Pi interpreta ese campo como estado real del gripper.
- El movimiento utiliza DR_MV_MOD_REL, por lo que los seis primeros valores recibidos son desplazamientos relativos y no una pose absoluta, de acuerdo con el código transcrito.
- El hilo de transmisión comparte sock_id con el bucle principal. La secuencia de cierre y thread_stop() debe probarse especialmente durante desconexiones para evitar escrituras sobre un socket ya cerrado.
- Los valores de velocidad y aceleración están fijados en el código como 200 y 200; cualquier cambio de proceso debería validarse en el entorno seguro del robot.

# 15\. Referencia al código fuente

Esta documentación se elaboró a partir del archivo **_raspberry2.drl_** y de la descripción funcional descrita en la arquitectura Robot Doosan ↔ Raspberry Pi 5. El script contiene la apertura del socket, el hilo de transmisión, el procesamiento de siete campos, el movimiento relativo, el control de DO\[8\], la consulta de pose y la recuperación ante errores.