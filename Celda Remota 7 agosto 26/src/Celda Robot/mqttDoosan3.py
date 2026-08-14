#1 LIBRERIAS Y VARIABLES
import time
import paho.mqtt.client as paho
from paho import mqtt
import threading
import json
import socket
import queue
import tkinter as tk
from tkinter import messagebox

# Colas seguras de comunicación entre hilos
cola_comandos = queue.Queue()
cola_config_robot = queue.Queue()

# Sockets y Clientes globales
sock = None
client_mqtt = None

# Banderas de control de hilos y estados deseados
hilo_robot_vivo = True
robot_debe_conectar = False  





#2. COMUNICACION ROBOT
def conectar_robot_fisico(ip, puerto, var_estado):
    """Maneja el intento de conexión socket puro fuera del entorno gráfico"""
    global sock
    try:
        if sock:
            try: sock.close()
            except: pass
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(3.0)
        sock.connect((ip, puerto))
        sock.settimeout(3.0) # Timeout prudente para esperar la telemetría del Trigger
        
        print(f"[TCP EXITO] Conectado físicamente a Doosan en {ip}:{puerto}")
        var_estado.set(True)
        
        #Levantamiento de Hilo de escucha        
        recv_thread = threading.Thread(target=receive_robot_position, args=(sock,), daemon=True)
        recv_thread.start()
        
        
        return True
    except Exception as e:
        print(f"[TCP ERROR] No se pudo conectar a {ip}:{puerto}: {e}")
        var_estado.set(False)
        sock = None
        return False

def hilo_procesador_robot():
    """Hilo único del robot: Envía comandos y lee la respuesta SÓLO si es un trigger (2.0)"""
    
    global sock, hilo_robot_vivo, robot_debe_conectar
    print("[HILO ROBOT] Inicializado y esperando condicionales de Trigger (Pose == 2.0)...")
    
    ip_actual = None
    puerto_actual = None
    var_estado_interfaz = None
    
    while hilo_robot_vivo:
        try:
            try:
                config_red = cola_config_robot.get_nowait()
                ip_actual = config_red['ip']
                puerto_actual = config_red['puerto']
                var_estado_interfaz = config_red['var_estado']
            except queue.Empty:
                pass
            
            if not robot_debe_conectar:
                if sock:
                    print("[TCP] Desconexión solicitada por el usuario.")
                    try: sock.close()
                    except: pass
                    sock = None
                    if var_estado_interfaz:
                        var_estado_interfaz.set(False)
                time.sleep(0.2)
                continue
                
            if ip_actual is None:
                time.sleep(0.2)
                continue
                
            if sock is None:
                exito = conectar_robot_fisico(ip_actual, puerto_actual, var_estado_interfaz)
                if not exito:
                    time.sleep(3)
                    continue
            
            # Obtener comando de la cola
            try:
                comando = cola_comandos.get(timeout=0.1)
            except queue.Empty:
                continue
                
            try:
                # 1. Enviar coordenadas al robot de forma inmediata
                mensaje = f"{comando['dx']},{comando['dy']},{comando['dz']},{comando['rx']},{comando['ry']},{comando['rz']},{comando['pinza']}\n"
                sock.sendall(mensaje.encode('utf-8'))
                
                # 2. EVALUACIÓN DE RESPUESTA: Solo leemos el socket si el comando fue un Trigger (2.0)
                if comando['pinza'] == 2.0:
                    print("[GUI TCP] Esperando la telemetría solicitada por el Trigger...")
                    raw_data = sock.recv(1024)
                    if raw_data:
                        trama = raw_data.decode('utf-8').strip().split('\n')[-1]
                        tokens = trama.split(",")
                        if len(tokens) >= 7:
                            lista_final = [
                                float(tokens[0]), float(tokens[1]), float(tokens[2]),
                                float(tokens[3]), float(tokens[4]), float(tokens[5]),
                                float(tokens[6])
                            ]
                            # Publicar de forma directa en el broker MQTT
                            publicar_telemetria_robot(lista_final)
                        
                time.sleep(0.01)
            except Exception as e:
                print(f"[TCP CAÍDA] Error durante el flujo de la condición: {e}")
                sock = None
                if var_estado_interfaz:
                    var_estado_interfaz.set(False)
                cola_comandos.put(comando)
                
            cola_comandos.task_done()
            
        except Exception as e:
            print(f"[ERROR BUCLE ROBOT] {e}")
            time.sleep(1)


 
 #3 GESTION MQTT         
def publicar_telemetria_robot(lista_datos):
    """Publica la lista de 7 variables en el tópico 'realPose'"""
    global client_mqtt
    if client_mqtt and client_mqtt.is_connected():
        try:            
            payload_json = json.dumps({"robotPose": lista_datos})
            client_mqtt.publish("robotPose", payload_json, qos=0)
            print(f"[MQTT TELEMETRIA] Publicado con éxito: {payload_json}")
        except Exception as e:
            print(f"[MQTT ERROR] No se pudo publicar telemetría: {e}")

def publicar_estado_sistema():
    """Publica una lista de 3 números [robot, mqtt, 0] en el tópico status"""
    global client_mqtt, sock
    if client_mqtt and client_mqtt.is_connected():
        robot_status = 1 if sock is not None else 0
        mqtt_status = 1
        tercer_num = 0
        
        payload = [robot_status, mqtt_status, tercer_num]
        try:
            client_mqtt.publish("status", json.dumps(payload), qos=1)
            print(f"[MQTT STATUS] Estado publicado: {payload}")
        except Exception as e:
            print(f"[MQTT STATUS ERROR] No se pudo publicar el estado: {e}")

def iniciar_mqtt_broker(config, var_mqtt):
    """Inicializa la comunicación con HiveMQ Cloud de forma asíncrona"""
    global client_mqtt
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("[MQTT] Conectado exitosamente con HiveMQ Cloud")
            var_mqtt.set(True)
            client.subscribe("pose")
            publicar_estado_sistema()
        else:
            print(f"[MQTT] Error de conexión. Código: {rc}")
            var_mqtt.set(False)

    def on_disconnect(client, userdata, rc):
        print("[MQTT] Desconectado del broker")
        var_mqtt.set(False)

    def on_message(client, userdata, msg):
        payload_str = msg.payload.decode("utf-8")
        if msg.topic == "pose":        
            try:
                listpose = json.loads(payload_str)
                if isinstance(listpose, list) and len(listpose) >= 7:            
                    dx = max(-400, min(listpose[0], 400))
                    dy = max(-400, min(listpose[1], 400))
                    dz = max(-400, min(listpose[2], 400))
                    rx = max(-10, min(listpose[3], 10))
                    ry = max(-10, min(listpose[4], 10))
                    rz = max(-10, min(listpose[5], 10))
                    
                    # FILTRO DE CONVERSIÓN DE LA VARIABLE 7:
                    # Si el valor de la pinza es exactamente 2.0, lo dejamos pasar intacto como Trigger para que Doosan envie datos pose del robot
                    if listpose[6] == 2.0:
                        pinza = 2.0
                    else:
                        # Si es cualquier otro valor, aplicamos tu mapeo binario normal (1.0 o 0.0)
                        pinza = 1.0 if listpose[6] > 0.1 else 0.0
                    
                    cola_comandos.put({
                        'dx': dx, 'dy': dy, 'dz': dz,
                        'rx': rx, 'ry': ry, 'rz': rz,
                        'pinza': pinza
                    })
            except Exception as e:
                print(f"[MQTT INVALID DATA] {e}")

    try:
        client_mqtt = paho.Client()
        client_mqtt.username_pw_set(config['mqtt_user'], config['mqtt_pass'])
        client_mqtt.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
        client_mqtt.on_connect = on_connect
        client_mqtt.on_disconnect = on_disconnect
        client_mqtt.on_message = on_message
        
        client_mqtt.connect(config['mqtt_url'], config['mqtt_port'], 60)
        client_mqtt.loop_start()
        return True
    except Exception as e:
        messagebox.showerror("Error MQTT", f"Fallo al enlazar con HiveMQ:\n{e}")
        return False

def detener_mqtt_broker():
    """Detiene y desconecta el cliente MQTT de manera limpia"""
    global client_mqtt
    if client_mqtt:
        try:
            try:
                payload = [0, 0, 0]
                client_mqtt.publish("status", json.dumps(payload), qos=1)
                time.sleep(0.2)
            except:
                pass
            client_mqtt.loop_stop()
            client_mqtt.disconnect()
            print("[MQTT] Bucle de red detenido.")
        except Exception as e:
            print(f"[MQTT ERROR AL CERRAR] {e}")
        client_mqtt = None




#4 INTERFAZ GRAFICA
class AppControl:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Comunicaciones Robot & MQTT")
        self.root.geometry("640x420")
        self.root.resizable(False, False)
        
        self.robot_conectado = tk.BooleanVar(value=False)
        self.mqtt_conectado = tk.BooleanVar(value=False)
        
        self.crear_widgets()
        
        self.robot_conectado.trace_add("write", lambda *args: self.actualizar_indicadores())
        self.mqtt_conectado.trace_add("write", lambda *args: self.actualizar_indicadores())

    def crear_widgets(self):
        # --- SECCIÓN ROBOT DOOSAN ---
        lbl_robot = tk.LabelFrame(self.root, text=" Configuración Robot Doosan ", padx=15, pady=10)
        lbl_robot.pack(fill="x", padx=15, pady=10)
        
        tk.Label(lbl_robot, text="IP:").grid(row=0, column=0, sticky="w")
        self.ent_ip = tk.Entry(lbl_robot, width=18)
        self.ent_ip.insert(0, "192.168.1.10")
        self.ent_ip.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        tk.Label(lbl_robot, text="Puerto:").grid(row=0, column=2, sticky="w", padx=10)
        self.ent_port = tk.Entry(lbl_robot, width=8)
        self.ent_port.insert(0, "20002")
        self.ent_port.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        
        self.btn_robot = tk.Button(lbl_robot, text="Conectar Robot", command=self.toggle_robot, bg="#2ecc71", fg="white", font=("Arial", 9, "bold"), width=16)
        self.btn_robot.grid(row=1, column=1, pady=8, sticky="w", padx=5)
        
        self.ind_robot = tk.Label(lbl_robot, text="  ", bg="red", width=2, relief="sunken")
        self.ind_robot.grid(row=1, column=2, padx=10, pady=8, sticky="e")
        self.lbl_txt_robot = tk.Label(lbl_robot, text="Desconectado", font=("Arial", 9))
        self.lbl_txt_robot.grid(row=1, column=3, sticky="w", pady=8, columnspan=2)

        # --- SECCIÓN MQTT BROKER ---
        lbl_mqtt = tk.LabelFrame(self.root, text=" Configuración MQTT HiveMQ ", padx=15, pady=10)
        lbl_mqtt.pack(fill="x", padx=15, pady=10)
        
        tk.Label(lbl_mqtt, text="URL Broker:").grid(row=0, column=0, sticky="w")
        self.ent_url = tk.Entry(lbl_mqtt, width=54)
        self.ent_url.insert(0, "0319358e340a4537960aa39a9b9b32cc.s1.eu.hivemq.cloud")
        self.ent_url.grid(row=0, column=1, columnspan=3, padx=5, pady=4, sticky="w")
        
        tk.Label(lbl_mqtt, text="Puerto:").grid(row=1, column=0, sticky="w")
        self.ent_mqport = tk.Entry(lbl_mqtt, width=10)
        self.ent_mqport.insert(0, "8883")
        self.ent_mqport.grid(row=1, column=1, padx=5, pady=4, sticky="w")
        
        tk.Label(lbl_mqtt, text="Usuario:").grid(row=2, column=0, sticky="w")
        self.ent_user = tk.Entry(lbl_mqtt, width=18)
        self.ent_user.insert(0, "Automatica_Lab")
        self.ent_user.grid(row=2, column=1, padx=5, pady=4, sticky="w")
        
        tk.Label(lbl_mqtt, text="Contraseña:").grid(row=2, column=2, sticky="w", padx=10)
        self.ent_pass = tk.Entry(lbl_mqtt, width=18, show="*")
        self.ent_pass.insert(0, "aLab0123456789")
        self.ent_pass.grid(row=2, column=3, padx=5, pady=4, sticky="w")
        
        self.btn_mqtt = tk.Button(lbl_mqtt, text="Conectar MQTT", command=self.toggle_mqtt, bg="#2ecc71", fg="white", font=("Arial", 9, "bold"), width=16)
        self.btn_mqtt.grid(row=3, column=1, pady=10, sticky="w", padx=5)
        
        self.ind_mqtt = tk.Label(lbl_mqtt, text="  ", bg="red", width=2, relief="sunken")
        self.ind_mqtt.grid(row=3, column=2, padx=10, pady=10, sticky="e")
        self.lbl_txt_mqtt = tk.Label(lbl_mqtt, text="Desconectado", font=("Arial", 9))
        self.lbl_txt_mqtt.grid(row=3, column=3, sticky="w", pady=10, columnspan=2)







    #5 LOGICA DE INTERFAZ Y CIERRE
    def actualizar_indicadores(self):
        global robot_debe_conectar
        if self.robot_conectado.get():
            self.ind_robot.config(bg="green")
            self.lbl_txt_robot.config(text="CONECTADO")
        else:
            self.ind_robot.config(bg="red")
            if robot_debe_conectar:
                self.lbl_txt_robot.config(text="Reintentando...")
            else:
                self.lbl_txt_robot.config(text="Desconectado")
            
        if self.mqtt_conectado.get():
            self.ind_mqtt.config(bg="green")
            self.lbl_txt_mqtt.config(text="CONECTADO")
        else:
            self.ind_mqtt.config(bg="red")
            self.lbl_txt_mqtt.config(text="Desconectado")
            
        publicar_estado_sistema()

    def toggle_robot(self):
        global robot_debe_conectar
        if not robot_debe_conectar:
            try:
                r_ip = self.ent_ip.get().strip()
                r_port = int(self.ent_port.get().strip())
            except ValueError:
                messagebox.showerror("Error de Datos", "El puerto del robot debe ser un número entero.")
                return
                
            robot_debe_conectar = True
            self.ent_ip.config(state="disabled")
            self.ent_port.config(state="disabled")
            self.btn_robot.config(text="Desconectar Robot", bg="#e74c3c")
            
            cola_config_robot.put({'ip': r_ip, 'puerto': r_port, 'var_estado': self.robot_conectado})
        else:
            robot_debe_conectar = False
            self.ent_ip.config(state="normal")
            self.ent_port.config(state="normal")
            self.btn_robot.config(text="Conectar Robot", bg="#2ecc71")
            self.root.after(100, publicar_estado_sistema)

    def toggle_mqtt(self):
        global client_mqtt
        if client_mqtt is None:
            try:
                config_mqtt = {
                    'mqtt_url': self.ent_url.get().strip(),
                    'mqtt_port': int(self.ent_mqport.get().strip()),
                    'mqtt_user': self.ent_user.get().strip(),
                    'mqtt_pass': self.ent_pass.get().strip()
                }
            except ValueError:
                messagebox.showerror("Error de Datos", "El puerto MQTT debe ser un número entero.")
                return
                
            self.ent_url.config(state="disabled")
            self.ent_mqport.config(state="disabled")
            self.ent_user.config(state="disabled")
            self.ent_pass.config(state="disabled")
            self.btn_mqtt.config(text="Desconectar MQTT", bg="#e74c3c")
            
            iniciar_mqtt_broker(config_mqtt, self.mqtt_conectado)
        else:
            detener_mqtt_broker()
            self.mqtt_conectado.set(False)
            
            self.ent_url.config(state="normal")
            self.ent_mqport.config(state="normal")
            self.ent_user.config(state="normal")
            self.ent_pass.config(state="normal")
            self.btn_mqtt.config(text="Conectar MQTT", bg="#2ecc71")

def al_cerrar_ventana():
    global hilo_robot_vivo, sock, robot_debe_conectar
    print("[SISTEMA] Cerrando aplicación de forma ordenada...")
    hilo_robot_vivo = False
    robot_debe_conectar = False
    detener_mqtt_broker()
    if sock:
        try: sock.close()
        except: pass
    root.destroy()
    
# Hilo para recibir continuamente la posición del TCP desde el Robot
def receive_robot_position(connection):
    # Buffer para acumular fragmentos de string de red
    buffer = ""
    while True:
        try:
            data = connection.recv(1024).decode('utf-8')
            if not data:
                break
            buffer += data
            
            # Procesar si hay saltos de línea (delimitador \n enviado por DRL)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if line:
                    # Convierte la cadena en una lista de floats [X, Y, Z, Rx, Ry, Rz]
                    tcp_coordinates = [int(float(val)) for val in line.split(",")]
                    print(f"[TCP Posición Robot]: {tcp_coordinates}")
                    try:
                        publicar_telemetria_robot(tcp_coordinates)                        
                    except:
                        continue
                        
        
        except TimeoutError: 
            continue
        except Exception as e:
            print(f"Error recibiendo datos: {e}")
            break




if __name__ == "__main__":
    # --- ARRANQUE ÚNICO DEL HILO EMISOR PRINCIPAL ---
    hilo_sistema_robot = threading.Thread(target=hilo_procesador_robot, daemon=True)
    hilo_sistema_robot.start()
    
    # --- INICIALIZACIÓN DE INTERFAZ GRÁFICA ---
    root = tk.Tk()
    app = AppControl(root)
    root.protocol("WM_DELETE_WINDOW", al_cerrar_ventana)
    root.mainloop()



