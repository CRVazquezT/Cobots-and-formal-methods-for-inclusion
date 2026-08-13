**COBOT PARA INCLUSION:**

**estación de operador**

**Versión: 7 agosto 2026**

**Subestación: Celda robot**

**Nombre de script: XRtest4.apk**

**Descripción: Aplicación Meta Quest 3 - Unity / Meta XR**

# 1\. Alcance y objetivo

Esta documentación describe exclusivamente el proyecto Unity suministrado para ejecutarse en Meta Quest 3. El alcance comprende la aplicación XR, la escena principal, los scripts propios, la representación de voxels, la representación de la pinza real, la interacción con la pinza virtual, el protocolo TCP implementado en el cliente Unity y los componentes auxiliares de interfaz y XR.

La arquitectura global que incluye Raspberry Pi, HiveMQ/MQTT y robot Doosan queda deliberadamente fuera de este documento. En esta fase únicamente se describe la interfaz TCP tal como está implementada dentro del proyecto Quest.

# 2\. Identificación del proyecto

| Elemento            | Valor                                   |
| ------------------- | --------------------------------------- |
| Editor Unity        | 6000.3.6f1                              |
| Plataforma objetivo | Meta Quest 3                            |
| Escena principal    | Assets/Scenes/SceneCobotVoxelsTCP.unity |
| Escena alternativa  | Assets/SceneCobotVoxelsTCPv0.unity      |
| Meta XR SDK         | com.meta.xr.sdk.all 203.0.0             |
| Render Pipeline     | Universal Render Pipeline 17.3.0        |
| Input System        | 1.18.0                                  |
| JSON                | Newtonsoft Json 3.2.2 + JsonUtility     |

# 3\. Descripción funcional

La aplicación combina realidad aumentada y objetos 3D interactivos. El proyecto incluye un modelo de mesa, modelos asociados al robot y al gripper, una referencia espacial y un conjunto de cubos utilizados para representar voxels.

- Recibir por TCP/IP datos JSON que contienen puntos/voxels y una pose de robot.
- Mantener los datos recibidos en variables estáticas accesibles por los componentes de la escena.
- Representar hasta 1500 voxels mediante cubos, usando posición y RGB.
- Actualizar la representación visual de la pinza real a partir de robotPose.
- Permitir la interacción del usuario con una pinza virtual.
- Calcular un desplazamiento objetivo a partir de la posición de la pinza virtual.
- Enviar por TCP comandos de movimiento, apertura/cierre del gripper y trigger de voxels.

# 4\. Arquitectura interna del proyecto

META QUEST 3  
![](data:image/png;base64,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)

# 5\. Escena principal

La escena documentada es SceneCobotVoxelsTCP.unity. A partir del archivo de escena se identifican, entre otros, los GameObjects propios que alojan los scripts principales.

| GameObject             | Script                      | Función                                             |
| ---------------------- | --------------------------- | --------------------------------------------------- |
| CommTCP                | ReceptorTCP                 | Cliente TCP y generación de comandos JSON.          |
| Variables Globales     | ContenedorVariables         | Inicialización/almacenamiento de datos globales.    |
| AssetsMotionController | VoxelsHandler               | Actualización de voxels y pinza real.               |
| GeneradorCubos         | GestorCubos                 | Generación de cubos para los voxels.                |
| InteraccionMesa        | ControladorManoInteractable | Habilitación/deshabilitación del agarre de la mesa. |
| SimuladorBotonPieza    | SimuladorBoton              | Ejecución automática de una acción UI.              |
| CierreApp              | ExitController              | Cierre de la aplicación.                            |

Además, el proyecto contiene escenas de recuperación y una escena SceneCobotVoxelsTCPv0. Algunos scripts auxiliares aparecen en escenas alternativas/de recuperación; esta documentación funcional se centra en la escena principal.

# 6\. Scripts propios

| Script                    | Responsabilidad                                            |
| ------------------------- | ---------------------------------------------------------- |
| ReceptorTCP.cs            | Comunicación TCP, recepción JSON y envío de comandos.      |
| ContenedorVariables.cs    | Almacenamiento estático de voxels y pose.                  |
| VoxelsHandler.cs          | Procesamiento visual de voxels y pinza real.               |
| GestorCubos.cs            | Creación de la reserva de cubos.                           |
| ControladorAgarre.cs      | Control de HandGrabInteractable y estado visual del botón. |
| SimuladorBoton.cs         | Ejecución periódica automática de un Button.               |
| SeguirHijo.cs             | Seguimiento espacial de un Transform.                      |
| LockRotation.cs           | Bloqueo de rotación mediante botón del controlador.        |
| estabilizarPassthrough.cs | Configuración de refresco/VSync XR.                        |
| ExitController.cs         | Cierre de la aplicación.                                   |

# 7\. ReceptorTCP: conexión y ciclo de recepción

ReceptorTCP implementa el cliente TCP de la aplicación. El puerto configurado es 9999 y la IP puede introducirse mediante un TMP_InputField. Existe una IP por defecto de 192.168.43.114.

La activación del cliente crea un hilo de fondo (BucleClienteTCP). El hilo intenta establecer la conexión y, una vez conectado, obtiene el NetworkStream y ejecuta LeerDatos(). Si se produce un fallo mientras el cliente sigue habilitado, espera 2 segundos y vuelve a intentar la conexión.

La lectura utiliza StreamReader.ReadLine(), por lo que cada mensaje se espera delimitado por un carácter de salto de línea. El hilo se ejecuta fuera del hilo principal de Unity.

# 8\. Modelo JSON recibido

La clase DatosProyecto define dos campos:

{"puntos": \[\[X,Y,Z,R,G,B\], ...\], "robotPose": \[X,Y,Z,RX,RY,RZ\]}

| Campo     | Tipo                  | Tratamiento                                                                    |
| --------- | --------------------- | ------------------------------------------------------------------------------ |
| puntos    | List&lt;List<int&gt;> | Se copia a ContenedorVariables.datosVoxels cuando existe y contiene elementos. |
| robotPose | List&lt;int&gt;       | Se copia a ContenedorVariables.robotPose cuando existe y contiene elementos.   |

La deserialización se realiza mediante Newtonsoft.Json. Los errores de formato JSON se registran como errores de la aplicación.

# 9\. Modelo JSON enviado

La clase DatosParaRaspberry define los campos utilizados para las acciones iniciadas desde Quest.

| Campo                 | Tipo            | Función                                                  |
| --------------------- | --------------- | -------------------------------------------------------- |
| abrirGripper          | bool            | Indica una orden de apertura.                            |
| cerrarGripper         | bool            | Indica una orden de cierre.                              |
| moverRobot            | bool            | Indica que se solicita un movimiento.                    |
| voxelsTrigger         | bool            | Indica una solicitud de actualización/trigger de voxels. |
| coordenadasMoverRobot | List&lt;int&gt; | Vector de seis valores asociado al movimiento.           |

{"abrirGripper":false,"cerrarGripper":false,"moverRobot":true,"voxelsTrigger":false,"coordenadasMoverRobot":\[X,Y,Z,RX,RY,RZ\]}

El JSON se genera con JsonUtility.ToJson(), se añade '\\n', se codifica en UTF-8 y se escribe en el NetworkStream.

# 10\. Comandos disponibles desde Quest

| Método               | moverRobot | Gripper     | Trigger |
| -------------------- | ---------- | ----------- | ------- |
| EnviarTrigger()      | false      | false       | true    |
| BotonAbrirGripper()  | false      | abrir=true  | false   |
| BotonCerrarGripper() | false      | cerrar=true | false   |
| BotonMoverRobot()    | true       | false       | false   |

# 11\. Cálculo de la posición objetivo de la pinza virtual

BotonMoverRobot() transforma la posición de pivoteGripperVirtual al sistema de referencia de referenceAsset. Primero se resta la posición del asset de referencia y se aplica la rotación inversa de dicho asset.

posArucoRobot_Aruco = Quaternion.Inverse(referenceAsset.rotation) \* (pivoteGripperVirtual.position - referenceAsset.position) \* 1000

El código utiliza una escala de 0.001 para interpretar milímetros frente a unidades de Unity; por ello, para obtener la posición en milímetros utiliza el inverso de esa escala.

Posteriormente se aplica la conversión de ejes implementada en el código y se utiliza una posición base posArucoBaseRobot_Aruco = \[340, -561, -28\]. Finalmente se resta robotPose para obtener el desplazamiento.

coordenadasMoverRobot = \[ΔX, ΔY, ΔZ, 0, 0, 0\]

Los tres últimos componentes se fijan en cero. Por tanto, el comando generado conserva explícitamente la orientación actual en lugar de solicitar una nueva orientación.

# 12\. Almacenamiento global: ContenedorVariables

ContenedorVariables utiliza variables estáticas para que distintos componentes puedan compartir los datos.

| Variable     | Tipo                  | Inicialización                                |
| ------------ | --------------------- | --------------------------------------------- |
| datosVoxels  | List&lt;List<int&gt;> | 1500 filas × 6 enteros, inicialmente en cero. |
| numeroVoxels | int                   | 1500.                                         |
| robotPose    | List&lt;int&gt;       | 6 enteros, inicialmente en cero.              |

La inicialización de datosVoxels se ejecuta mediante RuntimeInitializeOnLoadMethod antes de la carga de la escena.

# 13\. GestorCubos

GestorCubos genera en Awake() una lista de 1500 GameObjects. Cada uno recibe MeshFilter y MeshRenderer y utiliza la malla Cube.fbx incorporada en Unity.

- Los cubos se crean como hermanos del cubo de referencia, conservando el mismo padre.
- Se copian posición, rotación y escala locales del cubo de referencia.
- Se reutiliza el material compartido del cubo de referencia cuando está disponible.
- La lista resultante se expone mediante ObtenerListaCubos().

# 14\. VoxelsHandler

VoxelsHandler coordina la actualización de la representación visual de los voxels y de la pinza real.

Al ejecutar OnButtonClick(), obtiene los datos almacenados en ContenedorVariables, solicita un trigger mediante ReceptorTCP y actualiza la lista de cubos.

## 14.1 Transformación de voxels

- Cada voxel se interpreta como \[X,Y,Z,R,G,B\].
- La coordenada Z se invierte: Z' = -Z.
- Las coordenadas se multiplican por 0.001 para pasar de milímetros a unidades de Unity.
- El desplazamiento se rota mediante referenceAsset.transform.rotation.
- R, G y B se convierten a Color32 con alfa 255.
- Los cubos sin datos válidos se vuelven transparentes mediante alfa 0.

# 14.2 Flujo de actualización

# ![](data:image/png;base64,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)

# 15\. Representación de la pinza real

VoxelsHandler utiliza pivoteGripperReal para representar la posición del gripper real. La orientación del pivote se iguala a la de referenceAsset.

La posición se obtiene a partir de robotPose y de la posición base \[340, -561, -28\]. El código implementa una transformación de ejes según la relación indicada en sus comentarios: A.x = R.y, A.y = R.z y A.z = -R.x.

coordenadasGripper = \[robotPose\[1\]+(-561), robotPose\[2\]+(-28), -(robotPose\[0\]+340)\]

Finalmente la posición del pivote se expresa respecto de referenceAsset, utilizando la rotación del asset y la escala 0.001.

# 16\. Pinza virtual e interacción XR

ReceptorTCP mantiene la referencia pivoteGripperVirtual. Su posición es utilizada por BotonMoverRobot() como posición objetivo definida por el usuario.

El proyecto utiliza componentes de Meta XR para interacción. ControladorManoInteractable administra un HandGrabInteractable y permite alternar su habilitación desde un botón de UI.

# 17\. ControladorManoInteractable

El script ControladorAgarre.cs contiene la clase ControladorManoInteractable. Su función es sincronizar el estado del HandGrabInteractable con el aspecto de un botón.

| Estado                 | Visual                          |
| ---------------------- | ------------------------------- |
| HandGrab habilitado    | Color verde y texto 'Grabable'. |
| HandGrab deshabilitado | Color rojo y texto 'Bloqueado'. |

# 18\. SimuladorBoton

SimuladorBoton proporciona un modo automático para ejecutar periódicamente el onClick de un Button. Al activarse, cambia la interfaz a 'Parar' y ejecuta el botón cada 0.4 segundos. Al detenerse, restaura la interfaz a 'Automatico' y detiene las corrutinas.

# 19\. SeguirHijo

SeguirHijo conserva un desfase de posición y rotación respecto de assetHijo. El desfase se calcula en Start() y se aplica en LateUpdate(). Este mecanismo permite mantener una relación espacial estable después del tracking XR.

# 20\. LockRotation

LockRotation detecta OVRInput.Button.One, correspondiente al botón A del controlador derecho. Cada pulsación alterna el estado de bloqueo. Cuando está bloqueado, LateUpdate() restaura la rotación almacenada.

# 21\. Estabilización de Passthrough y refresco

EstabilizarPassthrough establece QualitySettings.vSyncCount = 1 y consulta el XRDisplaySubsystem activo. Si se obtienen tasas de refresco soportadas, solicita la primera y establece Application.targetFrameRate con ese valor.

# 22\. Cierre de la aplicación

ExitController.CerrarAplicacion() ejecuta Application.Quit(). Cuando se ejecuta dentro del editor de Unity, también detiene el modo Play mediante UnityEditor.EditorApplication.isPlaying.

# 23\. Assets 3D y materiales relevantes

| Asset                | Tipo      | Uso                             |
| -------------------- | --------- | ------------------------------- |
| MESA v1.obj          | Modelo 3D | Modelo de mesa.                 |
| Robot A0509-baza.obj | Modelo 3D | Modelo asociado al robot.       |
| RG2ligero.obj        | Modelo 3D | Modelo de gripper.              |
| gripperG2 (1).obj    | Modelo 3D | Modelo adicional de gripper.    |
| ARUCO42.jpg          | Imagen    | Recurso de marcador/referencia. |
| ColorVerde.mat       | Material  | Material verde.                 |
| ColorRojo.mat        | Material  | Material rojo.                  |
| RobotTraslucid.mat   | Material  | Material translúcido.           |
| materialMesa.mat     | Material  | Material de mesa.               |
| MaterialARUCO.mat    | Material  | Material asociado al marcador.  |

# 24\. Paquetes y dependencias principales

| Paquete                              | Versión |
| ------------------------------------ | ------- |
| com.meta.xr.sdk.all                  | 203.0.0 |
| com.unity.ai.navigation              | 2.0.9   |
| com.unity.inputsystem                | 1.18.0  |
| com.unity.nuget.newtonsoft-json      | 3.2.2   |
| com.unity.render-pipelines.universal | 17.3.0  |
| com.unity.ugui                       | 2.0.0   |
| com.unity.xr.management              | 4.5.4   |
| com.unity.xr.meta-openxr             | 2.5.1   |
| com.unity.xr.openxr                  | 1.16.1  |

# 25\. Flujo interno de operación

1. La aplicación inicia la configuración XR y la escena.
2. ContenedorVariables inicializa el almacenamiento para 1500 voxels y una pose de seis valores.
3. GestorCubos genera los cubos que serán utilizados para representar los voxels.
4. El usuario habilita el cliente TCP desde la interfaz.
5. ReceptorTCP crea su hilo de red y establece/reintenta la conexión.
6. Los mensajes JSON recibidos actualizan datosVoxels y robotPose.
7. Cuando se solicita la actualización visual, VoxelsHandler procesa los voxels y actualiza los cubos.
8. VoxelsHandler actualiza también la posición de la pinza real.
9. El usuario manipula la pinza virtual mediante los componentes XR.
10. BotonMoverRobot calcula el desplazamiento objetivo y ReceptorTCP envía el JSON.

# 26\. Diagrama de flujo de datos interno

![](data:image/png;base64,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)  
Usuario ──► Pinza virtual ──► BotonMoverRobot ──► ReceptorTCP ──► JSON

# 27\. Consideraciones técnicas

- La aplicación reserva 1500 cubos independientemente del número de voxels que llegue en cada actualización.
- El protocolo TCP utiliza '  
  ' como delimitador de mensajes.
- La lectura de red se realiza en un hilo de fondo para evitar bloquear el hilo principal de Unity.
- La transformación de coordenadas mediante referenceAsset es crítica para la correcta ubicación de voxels y pinzas.
- La coordenada Z de los voxels se invierte explícitamente durante su representación.
- La escala utilizada en la conversión de voxels y pose es 0.001.
- El movimiento generado desde la pinza virtual utiliza seis componentes, pero RX, RY y RZ se fijan en cero.
- La IP y el puerto forman parte de la configuración del cliente TCP y pueden ser modificados desde la interfaz de la aplicación.

# 28\. Conclusión

El proyecto constituye una aplicación XR para Meta Quest 3 basada en Unity y Meta XR. Sus componentes centrales son ReceptorTCP para la comunicación, ContenedorVariables para el estado compartido, GestorCubos y VoxelsHandler para la representación espacial, y los scripts de interacción para controlar la experiencia XR. El diseño permite recibir una representación de voxels y una pose, visualizarlas en la escena y generar desde la pinza virtual un desplazamiento que se transmite mediante TCP.