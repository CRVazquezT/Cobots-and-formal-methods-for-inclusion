#BLOQUE 1
import socket
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
import paho.mqtt.client as mqtt
import json

# Variables globales de control de red
mqtt_client = None
tcp_server = None
quest_socket = None
mqtt_connected = False
tcp_connected = False

global gripper_numerico
gripper_numerico=0.0

#Topic para mover robot o gripper
MQTT_TOPIC_POSE = "pose"  

def get_network_info():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_local = s.getsockname()[0]
        s.close()
    except Exception:
        ip_local = "127.0.0.1"

    try:
        ssid = subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
        if not ssid:
            ssid = "Ethernet / Cable"
    except Exception:
        ssid = "Desconectado"
    return ssid, ip_local

def update_network_display():
    ssid, ip_local = get_network_info()
    lbl_ssid_val.config(text=ssid)
    lbl_ip_val.config(text=ip_local)

def log(msg):
    root.after(0, _safe_log, msg)

def _safe_log(msg):
    txt_log.config(state="normal")
    txt_log.insert(tk.END, f"{msg}\n")
    txt_log.see(tk.END)
    txt_log.config(state="disabled")

# --- Inicialización de la interfaz Tkinter ---
root = tk.Tk()
root.title("mqtt Meta")
root.geometry("440x550")

# --- PANEL MQTT ---
f_mqtt = ttk.LabelFrame(root, text=" HiveMQ (MQTT) ", padding=10)
f_mqtt.pack(fill="x", padx=10, pady=5)
f_mqtt.columnconfigure(1, weight=1)

ttk.Label(f_mqtt, text="URL:").grid(row=0, column=0, sticky="w")
ent_url = ttk.Entry(f_mqtt)
ent_url.insert(0, "0319358e340a4537960aa39a9b9b32cc.s1.eu.hivemq.cloud")
ent_url.grid(row=0, column=1, sticky="ew")

ttk.Label(f_mqtt, text="Puerto:").grid(row=1, column=0, sticky="w")
ent_mport = ttk.Entry(f_mqtt)
ent_mport.insert(0, "8883")
ent_mport.grid(row=1, column=1, sticky="ew")

ttk.Label(f_mqtt, text="User:").grid(row=2, column=0, sticky="w")
ent_user = ttk.Entry(f_mqtt)
ent_user.insert(0, "Automatica_Lab")
ent_user.grid(row=2, column=1, sticky="ew")

ttk.Label(f_mqtt, text="Pass:").grid(row=3, column=0, sticky="w")
ent_pass = ttk.Entry(f_mqtt, show="*")
ent_pass.insert(0, "aLab0123456789")
ent_pass.grid(row=3, column=1, sticky="ew")

#Bloque 2
def on_mqtt_message(client, userdata, msg):
    """HILO 1: Recibe mensaje de MQTT (voxels y robotPose) y envía a Quest vía TCP"""
    global quest_socket
    payload = msg.payload.decode('utf-8')
    if quest_socket:
        try:
            quest_socket.sendall((payload + "\n").encode('utf-8'))
        except Exception:
            quest_socket = None
            log("Conexión perdida con Quest al enviar.")

def _async_mqtt_connect(url, port, u, p):
    """Proceso ejecutado en segundo plano para evitar colgar la interfaz gráfica"""
    global mqtt_client, mqtt_connected
    try:
        # Paho-mqtt requiere definir explícitamente la versión de compatibilidad del API
        try:
            from paho.mqtt.enums import CallbackAPIVersion
            mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION1)
        except ImportError:
            mqtt_client = mqtt.Client()

        if u and p:
            mqtt_client.username_pw_set(u, p)
        
        # SI USAS EL PUERTO SEGURO (8883), ACTIVA TLS DE FORMA OBLIGATORIA
        if port == 8883:
            # tls_set() sin argumentos usa los certificados raíz predeterminados del sistema operativo de la Pi
            mqtt_client.tls_set()
        
        mqtt_client.on_connect = lambda c, ud, f, rc: log("¡Conectado exitosamente a HiveMQ!") if rc==0 else log(f"Fallo de autenticación MQTT. Código: {rc}")
        mqtt_client.on_message = on_mqtt_message

        # Intentar conectar con un timeout estricto de 60 segundos
        mqtt_client.connect(url, port, keepalive=60)
        mqtt_client.loop_start()
        mqtt_client.subscribe("voxels")
        mqtt_client.subscribe("robotPose")
        mqtt_connected = True
        root.after(0, lambda: btn_mqtt.config(text="Desconectar MQTT"))
    except Exception as e:
        mqtt_connected = False
        root.after(0, lambda: btn_mqtt.config(text="Conectar MQTT"))
        log(f"Error al conectar MQTT: {e}")
        root.after(0, lambda: messagebox.showerror("Error de Conexión", f"No se pudo establecer enlace TLS con {url}:{port}\nVerifica la URL o tus credenciales."))

def toggle_mqtt():
    global mqtt_client, mqtt_connected
    if not mqtt_connected:
        btn_mqtt.config(text="Conectando...")
        log("Iniciando intento de conexión segura a HiveMQ...")
        
        # Validación automática de puerto en la interfaz gráfica
        try:
            puerto_entrada = int(ent_mport.get())
        except ValueError:
            messagebox.showerror("Error", "El puerto MQTT debe ser un número válido.")
            btn_mqtt.config(text="Conectar MQTT")
            return
            
        t = threading.Thread(
            target=_async_mqtt_connect, 
            args=(ent_url.get(), puerto_entrada, ent_user.get(), ent_pass.get()), 
            daemon=True
        )
        t.start()
    else:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        mqtt_connected = False
        btn_mqtt.config(text="Conectar MQTT")
        log("MQTT Desconectado.")

btn_mqtt = ttk.Button(f_mqtt, text="Conectar MQTT", command=toggle_mqtt)
btn_mqtt.grid(row=4, column=0, columnspan=2, pady=5)

# --- PANEL TCP ---
f_tcp = ttk.LabelFrame(root, text=" Meta Quest 3 (TCP Server) ", padding=10)
f_tcp.pack(fill="x", padx=10, pady=5)
f_tcp.columnconfigure(1, weight=1)

ttk.Label(f_tcp, text="Red Pi:").grid(row=0, column=0, sticky="w")
lbl_ssid_val = ttk.Label(f_tcp, text="...", font=("Arial", 9, "bold"), foreground="blue")
lbl_ssid_val.grid(row=0, column=1, sticky="w")

ttk.Label(f_tcp, text="IP Pi:").grid(row=1, column=0, sticky="w")
lbl_ip_val = ttk.Label(f_tcp, text="...", font=("Arial", 9, "bold"), foreground="green")
lbl_ip_val.grid(row=1, column=1, sticky="w")

ttk.Label(f_tcp, text="IP Escucha:").grid(row=2, column=0, sticky="w")
ent_tip = ttk.Entry(f_tcp)
ent_tip.insert(0, "0.0.0.0")
ent_tip.grid(row=2, column=1, sticky="ew")

ttk.Label(f_tcp, text="Puerto TCP:").grid(row=3, column=0, sticky="w")
ent_tport = ttk.Entry(f_tcp)
ent_tport.insert(0, "9999")
ent_tport.grid(row=3, column=1, sticky="ew")

def listen_tcp_loop():
    """HILO 2: Escucha al Quest 3 y publica en MQTT (fromQuest)"""
    global quest_socket, tcp_connected, mqtt_client, mqtt_connected
    while tcp_connected:
        try:
            log("Esperando conexión de Quest 3...")
            conn, addr = tcp_server.accept()
            quest_socket = conn
            log(f"Quest 3 conectado desde: {addr}")
            buffer = ""
            while tcp_connected:
                data = conn.recv(16384).decode('utf-8')

                if not data: break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip() and mqtt_client and mqtt_connected:
                        print(f"Mensaje recibido de Quest line: {line}")
                        #Hacer parsing y enviar datos a los topics correspondientes                        
                        try:
                            # 1. Convertir el JSON (string o bytes) a un diccionario de Python
                            datos = json.loads(line)
 
                            # 2. Extraer las 4 variables booleanas (con valores por defecto si no existen)
                            b1 = datos.get("abrirGripper", False)
                            b2 = datos.get("cerrarGripper", False)
                            b3 = datos.get("moverRobot", False)
                            b4 = datos.get("voxelsTrigger", False)
                            
                            # 3. Extraer la lista de enteros
                            coor_robot = datos.get("coordenadasMoverRobot", [])                            

                            # Imprimir resultados para verificar
                            print(f"Booleanos: {b1}, {b2}, {b3}, {b4}")
                            print(f"Coordenadas a mover robot: {coor_robot}")                                                    
                            
                            if (b1==True):
                                payload = (0.0,0.0,0.0,0.0,0.0,0.0,0.0)                                    
                                mensaje_json = json.dumps(list(payload))
                                gripper_numerico=0.0
                                try:
                                    mqtt_client.publish(MQTT_TOPIC_POSE, mensaje_json)
                                    print(f"Mensajes enviado a Mqtt: {mensaje_json}")
                                except: pass
                            if (b2==True):
                                payload = (0.0,0.0,0.0,0.0,0.0,0.0,1.0)                                    
                                mensaje_json = json.dumps(list(payload))
                                gripper_numerico=1.0
                                try:
                                    mqtt_client.publish(MQTT_TOPIC_POSE, mensaje_json)
                                    print(f"Mensajes enviado a Mqtt: {mensaje_json}")
                                except: pass
                            if (b3==True):
                                #ARREGLAR, YA QUE AQUI NO ESTOY OBLIGANDO A ABRIR/CERRAR GRIPPER
                                payload = (coor_robot[0],coor_robot[1],coor_robot[2],coor_robot[3],coor_robot[4],coor_robot[5],gripper_numerico)                                    
                                mensaje_json = json.dumps(list(payload))
                                print(f"Mensaje a enviar a Mqtt: {mensaje_json}")
                                try:
                                    mqtt_client.publish(MQTT_TOPIC_POSE, mensaje_json)
                                    print(f"Mensajes enviado a Mqtt: {mensaje_json}")
                                except: pass
                            if (b4==True):
                                try:
                                    mqtt_client.publish("voxelsTrigger", "True")
                                except: pass
                                    
                        except json.JSONDecodeError:
                            print("Error: El mensaje recibido no tiene un formato JSON válido.")
                        
        except Exception:
            pass
        finally:
            if quest_socket:
                try: quest_socket.close()
                except: pass
                quest_socket = None

def toggle_tcp():
    global tcp_server, quest_socket, tcp_connected
    if not tcp_connected:
        try:
            tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_server.bind((ent_tip.get(), int(ent_tport.get())))
            tcp_server.listen(1)
            tcp_connected = True
            btn_tcp.config(text="Detener TCP")
            threading.Thread(target=listen_tcp_loop, daemon=True).start()
            log(f"Servidor TCP listo en puerto {ent_tport.get()}")
        except Exception as e:
            messagebox.showerror("Error TCP", str(e))
    else:
        tcp_connected = False
        if quest_socket:
            try: quest_socket.close() 
            except: pass
            quest_socket = None
        if tcp_server:
            try: tcp_server.close()
            except: pass
        btn_tcp.config(text="Iniciar TCP")
        log("Servidor TCP detenido.")

ttk.Button(f_tcp, text="Ver Red", command=update_network_display).grid(row=4, column=0, pady=5)
btn_tcp = ttk.Button(f_tcp, text="Iniciar TCP", command=toggle_tcp)
btn_tcp.grid(row=4, column=1, pady=5, sticky="e")

# --- PANEL LOG ---
f_log = ttk.LabelFrame(root, text=" Log de Estado ", padding=10)
f_log.pack(fill="both", expand=True, padx=10, pady=5)
txt_log = tk.Text(f_log, height=6, state="disabled")
txt_log.pack(fill="both", expand=True)

# Ejecución inicial
update_network_display()
root.mainloop()


