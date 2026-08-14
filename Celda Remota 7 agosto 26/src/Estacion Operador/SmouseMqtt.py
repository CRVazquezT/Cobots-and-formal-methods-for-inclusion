import hid
import time
import threading
import tkinter as tk
from paho.mqtt.enums import CallbackAPIVersion
import paho.mqtt.client as mqtt
import json
from tkinter import messagebox, ttk


MODO = 3 
boton_izquierdo_presionado = False
MENSAJE = "Inicializando..."
sensibilidad=0.02
esta_bloqueado = True  # False significa que el sistema está "Desbloqueado" (Botón dice Bloquear)
CONTRASENA = "1234"  # Configura la contraseña numérica o de texto

# --- CONFIGURACIÓN DE CONEXIÓN (HIVEMQ CLOUD) ---
VENDOR_ID = 0x256F
PRODUCT_ID = 0xC63A

# Datos de HiveMQ
MQTT_BROKER = "0319358e340a4537960aa39a9b9b32cc.s1.eu.hivemq.cloud"  # El Hostname del Overview tab
MQTT_PORT = 8883                                   # Puerto TLS estándar para HiveMQ
MQTT_USER = "Automatica_Lab"                    # Creado en Access Management
MQTT_PASSWORD = "aLab0123456789"

MQTT_TOPIC_POSE = "pose"

# --- VARIABLES GLOBALES DE ESTADO ---
estado_mouse = {
    "x": 0, "y": 0, "z": 0,
    "rx": 0, "ry": 0, "rz": 0,
    "boton_izq":False, "boton_der":False
}



# --- HILO SECUNDARIO: SPACEMOUSE + MQTT ---
def hilo_background():
    global estado_mouse
    global MODO, boton_izquierdo_presionado
    global GRIPPER, boton_derecho_presionado
    global MENSAJE
    global gripper_numerico
    global sensibilidad
    global mqtt_conectado, cliente_mqtt
    
    mqtt_conectado = False
    cliente_mqtt = mqtt.Client()    
    cliente_mqtt.tls_set()  # Activa SSL/TLS seguro requerido en la nube

    # Inicializa esta variable al principio de tu script o en el constructor (__init__)
    ultimo_envio = 0
    INTERVALO_MINIMO = 0.1  # 0.05 segundos = 50 ms (ajusta este valor a tu gusto)
    
    boton_izquierdo_presionado = False  # Evita que el modo cambie infinitamente mientras mantienes presionado
    GRIPPER = False
    gripper_numerico=0.0
    boton_derecho_presionado = False  # Evita que el modo cambie infinitamente mientras mantienes presionado               

    # 2. Configurar e Inicializar SpaceMouse
    device = hid.device()
    try:
        device_path = None
        for d in hid.enumerate():
            if d['vendor_id'] == VENDOR_ID and d['product_id'] == PRODUCT_ID:
                device_path = d['path']
                break
                
        if device_path is None:
            print("Error: No se encontró el SpaceMouse Wireless.")
            MENSAJE="No se encontró el SpaceMouse Wireless"
            return

        device.open_path(device_path)
        device.set_nonblocking(True)
        print("SpaceMouse en línea y leyendo datos.")
        MENSAJE="SpaceMouse en línea y leyendo datos"
        
        while True:
            if esta_bloqueado == False:
                        
                data = device.read(64)
                if data:               
                    report_id = data[0]
                
                    # Solo envía si ha pasado el tiempo suficiente
                    tiempo_actual = time.time()
                    if tiempo_actual - ultimo_envio >= INTERVALO_MINIMO:             
                        # Procesar movimientos
                        if report_id == 1 and len(data) >= 13:
                            if MODO==1 or MODO==2 or MODO==3:
                                estado_mouse["x"] = sensibilidad*int.from_bytes(data[3:5], byteorder='little', signed=True)
                                estado_mouse["y"] = sensibilidad*int.from_bytes(data[1:3], byteorder='little', signed=True)
                                estado_mouse["z"] = sensibilidad*-1*int.from_bytes(data[5:7], byteorder='little', signed=True)
                                if MODO==3 and abs(estado_mouse["x"])>=abs(estado_mouse["y"]) and abs(estado_mouse["x"])>=abs(estado_mouse["z"]):
                                    estado_mouse["y"]=0
                                    estado_mouse["z"]=0
                                if MODO==3 and abs(estado_mouse["y"])>=abs(estado_mouse["x"]) and abs(estado_mouse["y"])>=abs(estado_mouse["z"]):
                                    estado_mouse["x"]=0
                                    estado_mouse["z"]=0
                                if MODO==3 and abs(estado_mouse["z"])>=abs(estado_mouse["x"]) and abs(estado_mouse["z"])>=abs(estado_mouse["y"]):
                                    estado_mouse["x"]=0
                                    estado_mouse["y"]=0
                            else:
                                estado_mouse["x"] = 0
                                estado_mouse["y"] = 0
                                estado_mouse["z"] = 0
                            if MODO==1 or MODO==4 or MODO==5:
                                estado_mouse["rx"] = sensibilidad*int.from_bytes(data[7:9], byteorder='little', signed=True)
                                estado_mouse["ry"] = sensibilidad*int.from_bytes(data[9:11], byteorder='little', signed=True)
                                estado_mouse["rz"] = -1*int.from_bytes(data[11:13], byteorder='little', signed=True)
                                if MODO==5 and abs(estado_mouse["rx"])>=abs(estado_mouse["ry"]) and abs(estado_mouse["rx"])>=abs(estado_mouse["rz"]):
                                    estado_mouse["ry"]=0
                                    estado_mouse["rz"]=0
                                if MODO==5 and abs(estado_mouse["ry"])>=abs(estado_mouse["rx"]) and abs(estado_mouse["ry"])>=abs(estado_mouse["rz"]):
                                    estado_mouse["rx"]=0
                                    estado_mouse["rz"]=0
                                if MODO==5 and abs(estado_mouse["rz"])>=abs(estado_mouse["rx"]) and abs(estado_mouse["rz"])>=abs(estado_mouse["ry"]):
                                    estado_mouse["rx"]=0
                                    estado_mouse["ry"]=0
                            else:
                                estado_mouse["rx"] = 0
                                estado_mouse["ry"] = 0
                                estado_mouse["rz"] = 0
                            #Se acotan los valores de movimiento dle robot
                            estado_mouse["x"]=max(-40,min(estado_mouse["x"],40))
                            estado_mouse["y"]=max(-40,min(estado_mouse["y"],40))
                            estado_mouse["z"]=max(-40,min(estado_mouse["z"],40))
                            estado_mouse["rx"]=max(-10,min(estado_mouse["rx"],10))
                            estado_mouse["ry"]=max(-10,min(estado_mouse["ry"],10))
                            estado_mouse["rz"]=max(-10,min(estado_mouse["rz"],10))
                            payload = (estado_mouse["x"],estado_mouse["y"],estado_mouse["z"],estado_mouse["rx"],estado_mouse["ry"],estado_mouse["rz"],gripper_numerico)
                            mensaje_json = json.dumps(list(payload))
                            try:
                                cliente_mqtt.publish(MQTT_TOPIC_POSE, mensaje_json)
                                print(f"Mensajes enviado a Mqtt: {mensaje_json}")
                            except: pass
                
                        # Procesar botones
                        elif report_id == 3 and len(data) >= 2:
                            byte_botones = data[1]
                            estado_mouse["boton_izq"] = (byte_botones & 0x01) != 0
                            estado_mouse["boton_der"] = (byte_botones & 0x02) != 0
                    
                            #Cambiar la variable MODO de acuerdo al boton izquierdo
                            # Lógica para cambiar el MODO (solo al presionar, no al mantener presionado)
                            if estado_mouse["boton_izq"] and not boton_izquierdo_presionado and not estado_mouse["boton_der"]:
                                boton_izquierdo_presionado = True
                                                            
                                if sensibilidad==0.02: sensibilidad=0.1
                                elif sensibilidad==0.1: sensibilidad=0.2
                                elif sensibilidad==0.2: sensibilidad=0.4
                                elif sensibilidad==0.4: sensibilidad=1
                                elif sensibilidad==1: sensibilidad=0.02
                            
                            if not estado_mouse["boton_izq"]:
                                # Se liberó el botón, listos para el siguiente clic
                                boton_izquierdo_presionado = False
                        
                            #Cambiar la variable GRIPPER de acuerdo al boton derecho
                            # Lógica para cambiar el GRIPPER (solo al presionar, no al mantener presionado)
                            if estado_mouse["boton_der"] and not boton_derecho_presionado and not estado_mouse["boton_izq"]:
                                boton_derecho_presionado = True                            
                                # Toogle
                                GRIPPER = not GRIPPER
                                if GRIPPER==True:
                                    payload = (0.0,0.0,0.0,0.0,0.0,0.0,0.0)
                                    gripper_numerico=0.0
                                    mensaje_json = json.dumps(list(payload))
                                    try:
                                        cliente_mqtt.publish(MQTT_TOPIC_POSE, mensaje_json)
                                        print(f"Mensajes enviado a Mqtt: {mensaje_json}")
                                    except: pass
                                elif GRIPPER==False:
                                    payload = (0.0,0.0,0.0,0.0,0.0,0.0,1.0)
                                    gripper_numerico=1.0
                                    mensaje_json = json.dumps(list(payload))
                                    try:
                                        cliente_mqtt.publish(MQTT_TOPIC_POSE, mensaje_json)
                                        print(f"Mensajes enviado a Mqtt: {mensaje_json}")
                                    except: pass
                            
                                #Enviar nuevo estado del Gripper a Mqtt
                                payload = f'{{"gripper":{str(GRIPPER)}}}'
                                try:
                                    cliente_mqtt.publish(MQTT_TOPIC_GRIPPER, payload)
                                    print(f"Mensajes enviado a Mqtt: {payload}")
                                except: pass
                            
                            if not estado_mouse["boton_der"]:
                                # Se liberó el botón, listos para el siguiente clic
                                boton_derecho_presionado = False
                            
                        ultimo_envio = tiempo_actual  # Actualiza el marcador de tiemp
                time.sleep(0.001)

            

    except IOError as e:
        print(f"Error en dispositivo HID: {e}")
    finally:
        try: device.close()
        except: pass
        cliente_mqtt.loop_stop()
        cliente_mqtt.disconnect()      



def alternar_conexion_mqtt():
    global mqtt_conectado, cliente_mqtt
    
    if not mqtt_conectado:                
        cliente_mqtt.username_pw_set(ent_user.get(), ent_pass.get())        
        # Configura las credenciales y el host de tu servidor
        cliente_mqtt.connect(ent_url.get().strip(), int(ent_mport.get().strip()), 60)
        # Inicia el bucle de red en segundo plano sin bloquear el programa
        cliente_mqtt.loop_start() 
        mqtt_conectado = True
        print(" Conectado exitosamente al servidor MQTT")
        boton_mqtt.config(text="Desconectar Hivemq")
    else:
        # Detiene el bucle de red de forma segura
        cliente_mqtt.loop_stop()
        cliente_mqtt.disconnect()
        mqtt_conectado = False
        print("Desconectado del servidor MQTT")
        boton_mqtt.config(text="Conectar Hivemq")

def accion_boton():
    print("¡Botón de Tkinter presionado!")

def actualizar_interfaz():
    global sensibilidad
    
    txt_izq = "ACTIVO" if estado_mouse["boton_izq"] else "INACTIVO"
    txt_der = "ACTIVO" if estado_mouse["boton_der"] else "INACTIVO"
    if MODO==1:
        label_modo.config(text=f"Modo: Normal")
    if MODO==2:
        label_modo.config(text=f"Modo: Traslación")
    if MODO==3:
        label_modo.config(text=f"Modo: Traslación 1-eje")
    if MODO==4:
        label_modo.config(text=f"Modo: Rotación")
    if MODO==5:
        label_modo.config(text=f"Modo: Rotación 1-eje")
    
    if GRIPPER==False:
        label_pinza.config(text=f"Commando a Pinza: Cerrar")
    if GRIPPER==True:
        label_pinza.config(text=f"Commando a Pinza: Abrir")
           
    label_sensibilidad.config(text=f"Sensibilidad: {sensibilidad:.2f}")
    
       
    label_mensaje.config(text=MENSAJE)
    ventana.after(100, actualizar_interfaz)
 
def cambiar_modo():
    global MODO
    # Ciclar entre 1 y5
    MODO = MODO + 1 if MODO < 5 else 1

def alternar_bloqueo():
    global esta_bloqueado
    
    # CASO 1: Está desbloqueado -> Pasamos a BLOQUEADO
    if not esta_bloqueado:
        esta_bloqueado = True
        boton_bloqueo.config(text="Desbloquear")
        
        # Mostramos los elementos cambiando el texto de la etiqueta
        etiqueta_pass.config(text="SISTEMA BLOQUEADO\nIngrese contraseña para desbloquear:")
        entrada_pass.pack(pady=5, before=boton_bloqueo)
        
        entrada_pass.delete(0, tk.END)  # Limpia el cuadro
        entrada_pass.focus()  # Pone el cursor en el cuadro
        
    # CASO 2: Está bloqueado -> Intentamos DESBLOQUEAR
    else:
        password_ingresado = entrada_pass.get()  # Extraemos el texto de forma segura
        
        if password_ingresado == CONTRASENA:
            esta_bloqueado = False
            boton_bloqueo.config(text="Bloquear")
            
            # Limpiamos la interfaz volviendo al estado inicial
            etiqueta_pass.config(text="Sistema Desbloqueado y Operativo")
            entrada_pass.pack_forget()  # Ocultamos la caja de texto
            entrada_pass.delete(0, tk.END)
        else:
            messagebox.showerror("Error de Seguridad", "Contraseña incorrecta. Inténtalo de nuevo.")
            entrada_pass.delete(0, tk.END)
            entrada_pass.focus()


# Construir Ventana
ventana = tk.Tk()
ventana.title("HiveMQ Cloud + SpaceMouse")
ventana.geometry("450x550")  # Se aumentó ligeramente el tamaño para dar aire al nuevo diseño

# --- PANEL MQTT ---
f_mqtt = ttk.LabelFrame(ventana, text=" Conexión HiveMQ (MQTT) ", padding=10)
f_mqtt.pack(fill="x", padx=10, pady=5)
f_mqtt.columnconfigure(1, weight=1)

tk.Label(f_mqtt, text="URL:").grid(row=0, column=0, sticky="w", pady=2)
ent_url = tk.Entry(f_mqtt)
ent_url.insert(0, "0319358e340a4537960aa39a9b9b32cc.s1.eu.hivemq.cloud")
ent_url.grid(row=0, column=1, sticky="ew", pady=2)

tk.Label(f_mqtt, text="Puerto:").grid(row=1, column=0, sticky="w", pady=2)
ent_mport = tk.Entry(f_mqtt)
ent_mport.insert(0, "8883")
ent_mport.grid(row=1, column=1, sticky="ew", pady=2)

tk.Label(f_mqtt, text="User:").grid(row=2, column=0, sticky="w", pady=2)
ent_user = tk.Entry(f_mqtt)
ent_user.insert(0, "Automatica_Lab")
ent_user.grid(row=2, column=1, sticky="ew", pady=2)

tk.Label(f_mqtt, text="Pass:").grid(row=3, column=0, sticky="w", pady=2)
ent_pass = tk.Entry(f_mqtt, show="*")
ent_pass.insert(0, "aLab0123456789")
ent_pass.grid(row=3, column=1, sticky="ew", pady=2)

# El botón de conexión ahora pertenece al panel de MQTT (f_mqtt)
boton_mqtt = tk.Button(f_mqtt, text="Conectar HiveMQ", command=alternar_conexion_mqtt, bg="#e1e1e1")
boton_mqtt.grid(row=4, column=0, columnspan=2, pady=(10, 2), sticky="ew")


# --- PANEL SPACEMOUSE CONTROL ---
f_control = ttk.LabelFrame(ventana, text=" SpaceMouse Control ", padding=10)
f_control.pack(fill="both", expand=True, padx=10, pady=5)

# Botón cambiar modo dentro del panel de control
boton = tk.Button(f_control, text="Cambiar Modo", command=cambiar_modo, width=15)
boton.pack(pady=5)

# Etiquetas de estados principales
label_modo = tk.Label(f_control, text="Modo: Normal", font=("Arial", 14, "bold"))
label_modo.pack(pady=2)

label_pinza = tk.Label(f_control, text="Comando a Pinza: Cerrar", font=("Arial", 14))
label_pinza.pack(pady=2)

label_sensibilidad = tk.Label(f_control, text="Sensibilidad: 0.02", font=("Arial", 14))
label_sensibilidad.pack(pady=2)

label_mensaje = tk.Label(f_control, text="Mensaje: Inicializando...", font=("Arial", 10), fg="gray")
label_mensaje.pack(pady=5)


# --- SECCIÓN DE SEGURIDAD / BLOQUEO ---
# Se mantiene al fondo de la ventana principal para separar el control activo de la seguridad
etiqueta_pass = tk.Label(ventana, text="SISTEMA BLOQUEADO\nIngrese contraseña para desbloquear:", font=("Arial", 10, "bold"), fg="red")
etiqueta_pass.pack(pady=(15, 2))

entrada_pass = tk.Entry(ventana, show="*", width=20, font=("Arial", 10), justify="center")
entrada_pass.pack(pady=2)

boton_bloqueo = tk.Button(ventana, text="Desbloquear", command=alternar_bloqueo, width=15, height=1)
boton_bloqueo.pack(pady=(2, 15))


# Ejecución asíncrona
hilo_mouse = threading.Thread(target=hilo_background, daemon=True)
hilo_mouse.start()

ventana.after(100, actualizar_interfaz)
ventana.mainloop()
