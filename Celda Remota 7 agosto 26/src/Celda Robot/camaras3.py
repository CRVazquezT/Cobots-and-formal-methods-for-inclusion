import tkinter as tk
from tkinter import messagebox, scrolledtext
import yaml
import subprocess
import os
import signal
import re
import sys

#GENERACION DE PATHS DINAMICOS PARA MEDIAMTX
# Base path para lo que va DENTRO del ejecutable (Lectura pura)
if getattr(sys, 'frozen', False):
    internal_base = sys._MEIPASS
else:
    internal_base = os.path.dirname(os.path.abspath(__file__))
# Base path para lo que va FUERA del ejecutable (Archivos modificables)
if getattr(sys, 'frozen', False):
    external_base = os.path.dirname(sys.executable)
else:
    external_base = os.path.dirname(os.path.abspath(__file__))
# RUTA PARA EL BINARIO (Se lee desde adentro de la app)
mediamtx_path = os.path.join(internal_base, 'mediamtx')

# RUTA PARA LA CONFIGURACIÓN (Se lee y MODIFICA afuera de la app)
config_path = os.path.join(external_base, 'mediamtx.yml')



#AQUI YA INICIA EL CODIGO GENERAL
class MediaMtxManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Cámaras Pro - MediaMTX")
        self.root.geometry("590x620")
        
        #self.config_path = "mediamtx.yml"
        self.config_path =config_path
        self.process = None

        # Variables de control para el formulario
        self.cam1_dev = tk.StringVar(value="/dev/video0")
        self.cam1_res = tk.StringVar(value="1280x720")
        self.cam1_fps = tk.StringVar(value="30")
        self.cam1_mjpeg = tk.BooleanVar(value=False)
        
        self.cam2_dev = tk.StringVar(value="/dev/video2")
        self.cam2_res = tk.StringVar(value="1280x720")
        self.cam2_fps = tk.StringVar(value="30")
        self.cam2_mjpeg = tk.BooleanVar(value=True)

        self.create_widgets()
        self.load_current_config()

    def create_widgets(self):
        # --- BUSCADOR GLOBAL ---
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=15)
        btn_list_all = tk.Button(top_frame, text="Listar Webcams Conectadas", command=self.show_all_devices, bg="#1A73E8", fg="white", font=("Arial", 10, "bold"))
        btn_list_all.pack()

        # --- CÁMARA 1 ---
        lbl_c1 = tk.Label(self.root, text="CÁMARA 1", font=("Arial", 11, "bold"), fg="#1A73E8")
        lbl_c1.pack(pady=(15, 2))
        
        f1 = tk.Frame(self.root)
        f1.pack(pady=5)
        tk.Label(f1, text="Dispositivo:").grid(row=0, column=0, padx=2)
        tk.Entry(f1, textvariable=self.cam1_dev, width=11).grid(row=0, column=1, padx=2)
        
        tk.Button(f1, text="Formatos", command=lambda: self.check_cam_capabilities(self.cam1_dev.get())).grid(row=0, column=2, padx=2)
        tk.Button(f1, text="Ver en vivo", command=lambda: self.play_local_video("webcam"), bg="#FF9800", fg="white", font=("Arial", 9, "bold")).grid(row=0, column=3, padx=5)
        
        tk.Label(f1, text="Res:").grid(row=0, column=4, padx=2)
        tk.Entry(f1, textvariable=self.cam1_res, width=10).grid(row=0, column=5, padx=2)
        tk.Label(f1, text="FPS:").grid(row=0, column=6, padx=2)
        tk.Entry(f1, textvariable=self.cam1_fps, width=4).grid(row=0, column=7, padx=2)
        
        chk_mjpeg1 = tk.Checkbutton(self.root, text="Activar compresión por hardware (-input_format mjpeg)", variable=self.cam1_mjpeg)
        chk_mjpeg1.pack(pady=(2, 10))

        # --- CÁMARA 2 ---
        lbl_c2 = tk.Label(self.root, text="CÁMARA 2", font=("Arial", 11, "bold"), fg="#1A73E8")
        lbl_c2.pack(pady=(15, 2))
        
        f2 = tk.Frame(self.root)
        f2.pack(pady=5)
        tk.Label(f2, text="Dispositivo:").grid(row=0, column=0, padx=2)
        tk.Entry(f2, textvariable=self.cam2_dev, width=11).grid(row=0, column=1, padx=2)
        
        tk.Button(f2, text="Formatos", command=lambda: self.check_cam_capabilities(self.cam2_dev.get())).grid(row=0, column=2, padx=2)
        tk.Button(f2, text="Ver en vivo", command=lambda: self.play_local_video("webcam2"), bg="#FF9800", fg="white", font=("Arial", 9, "bold")).grid(row=0, column=3, padx=5)
        
        tk.Label(f2, text="Res:").grid(row=0, column=4, padx=2)
        tk.Entry(f2, textvariable=self.cam2_res, width=10).grid(row=0, column=5, padx=2)
        tk.Label(f2, text="FPS:").grid(row=0, column=6, padx=2)
        tk.Entry(f2, textvariable=self.cam2_fps, width=4).grid(row=0, column=7, padx=2)
        
        chk_mjpeg2 = tk.Checkbutton(self.root, text="Activar compresión por hardware (-input_format mjpeg)", variable=self.cam2_mjpeg)
        chk_mjpeg2.pack(pady=(2, 10))

        # --- BOTONES DE ACCIÓN ---
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)

        self.btn_start = tk.Button(btn_frame, text="▶ Conectar Cámaras", command=self.connect_cameras, bg="#2E7D32", fg="white", font=("Arial", 10, "bold"), width=18)
        self.btn_start.grid(row=0, column=0, padx=10, ipady=5)

        self.btn_stop = tk.Button(btn_frame, text="⏹ Desconectar", command=self.disconnect_cameras, bg="#C62828", fg="white", font=("Arial", 10, "bold"), width=18, state=tk.DISABLED)
        self.btn_stop.grid(row=0, column=1, padx=10, ipady=5)

        # --- PANEL DE ESTADO ---
        self.status_card = tk.Frame(self.root, bg="#FFEBEE", bd=1, relief=tk.SOLID)
        self.status_card.pack(pady=15, fill=tk.X, padx=40)

        self.lbl_status = tk.Label(self.status_card, text="ESTADO: DESCONECTADO (Cámaras Apagadas)", fg="#C62828", bg="#FFEBEE", font=("Arial", 10, "bold"))
        self.lbl_status.pack(pady=10)

    def play_local_video(self, stream_path):
        """Lanza MPlayer apuntando al flujo local RTSP generado por MediaMTX"""
        if not self.process:
            messagebox.showwarning("Servidor Apagado", "Primero debes presionar '▶ Conectar Cámaras' para encender el servidor de transmisión antes de poder ver el video.")
            return
            
        try:
            # Comando optimizado para MPlayer: baja latencia, sin caché y omitiendo frames retrasados
            mplayer_cmd = [
                "mplayer", 
                f"rtsp://127.0.0.1:8554/{stream_path}", 
                "-nocache", 
                "-framedrop", 
                "-fps", "30"
            ]
            # Ejecuta MPlayer en un proceso independiente (no bloquea la app de Python)
            subprocess.Popen(mplayer_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            messagebox.showerror("MPlayer no encontrado", "MPlayer no está instalado en tu Raspberry Pi.\nInstálalo ejecutando en la terminal:\nsudo apt install mplayer")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar la previsualización: {e}")

    def show_all_devices(self):
        try:
            result = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            
            win = tk.Toplevel(self.root)
            win.title("Dispositivos de Video Disponibles")
            win.geometry("450x300")
            
            txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Monospace", 10))
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            txt.insert(tk.END, output if output else "No se detectaron webcams en los puertos USB.")
            txt.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo listar los dispositivos: {e}")

    def check_cam_capabilities(self, device_path):
        if not os.path.exists(device_path):
            messagebox.showerror("Error de Ruta", f"El dispositivo '{device_path}' no existe.\nVerifica si está bien conectado.")
            return

        try:
            result = subprocess.run(["v4l2-ctl", f"--device={device_path}", "--list-formats-ext"], capture_output=True, text=True, check=True)
            raw_output = result.stdout
            
            formatted_lines = []
            current_format = ""
            
            for line in raw_output.split('\n'):
                line_str = line.strip()
                if "Pixel Format:" in line_str:
                    current_format = line_str.replace("Pixel Format:", "Formato:")
                    formatted_lines.append(f"\n⚡ {current_format}")
                elif "Size: Discrete" in line_str:
                    res = line_str.replace("Size: Discrete", "  ↳ Resolución:")
                    formatted_lines.append(res)
                elif "Interval: Discrete" in line_str:
                    fps_match = re.search(r'\((.*?)\)', line_str)
                    if fps_match:
                        formatted_lines.append(f"      • {fps_match.group(1)}")

            output_clean = "\n".join(formatted_lines).strip()
            
            win = tk.Toplevel(self.root)
            win.title(f"Formatos Soportados - {os.path.basename(device_path)}")
            win.geometry("480x400")
            
            lbl_title = tk.Label(win, text=f"Especificaciones Reales para: {device_path}", font=("Arial", 10, "bold"), pady=5)
            lbl_title.pack()
            
            txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Monospace", 10), bg="#F5F5F5")
            txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            txt.insert(tk.END, output_clean if output_clean else "El dispositivo no reportó resoluciones válidas.")
            txt.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error de Lectura", f"No se pudieron extraer datos de {device_path}.\nDetalle: {e}")

    def load_current_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                paths = config.get('paths', {})
                
                if 'webcam' in paths and 'runOnInit' in paths['webcam']:
                    cmd = paths['webcam']['runOnInit']
                    parts = cmd.split()
                    self.cam1_mjpeg.set("-input_format" in parts and "mjpeg" in parts)
                    if '-video_size' in parts: self.cam1_res.set(parts[parts.index('-video_size')+1])
                    if '-framerate' in parts: self.cam1_fps.set(parts[parts.index('-framerate')+1])
                    if '-i' in parts: self.cam1_dev.set(parts[parts.index('-i')+1])

                if 'webcam2' in paths and 'runOnInit' in paths['webcam2']:
                    cmd = paths['webcam2']['runOnInit']
                    parts = cmd.split()
                    self.cam2_mjpeg.set("-input_format" in parts and "mjpeg" in parts)
                    if '-video_size' in parts: self.cam2_res.set(parts[parts.index('-video_size')+1])
                    if '-framerate' in parts: self.cam2_fps.set(parts[parts.index('-framerate')+1])
                    if '-i' in parts: self.cam2_dev.set(parts[parts.index('-i')+1])
        except Exception as e:
            print(f"Aviso al cargar configuración: {e}")

    def save_parameters_to_yml(self):
        try:
            config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
            
            if 'paths' not in config:
                config['paths'] = {}

            mjpeg_arg_c1 = "-input_format mjpeg " if self.cam1_mjpeg.get() else ""
            mjpeg_arg_c2 = "-input_format mjpeg " if self.cam2_mjpeg.get() else ""

            cmd_cam1 = f"ffmpeg -f v4l2 {mjpeg_arg_c1}-video_size {self.cam1_res.get()} -framerate {self.cam1_fps.get()} -i {self.cam1_dev.get()} -c:v libx264 -preset ultrafast -tune zerolatency -f rtsp rtsp://localhost:$RTSP_PORT/$MTX_PATH"
            cmd_cam2 = f"ffmpeg -f v4l2 {mjpeg_arg_c2}-video_size {self.cam2_res.get()} -framerate {self.cam2_fps.get()} -i {self.cam2_dev.get()} -c:v libx264 -preset ultrafast -tune zerolatency -f rtsp rtsp://localhost:$RTSP_PORT/$MTX_PATH"

            config['paths']['webcam'] = {'runOnInit': cmd_cam1, 'runOnInitRestart': True}
            config['paths']['webcam2'] = {'runOnInit': cmd_cam2, 'runOnInitRestart': True}

            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo escribir la configuración: {e}")
            return False

    def connect_cameras(self):
        if self.save_parameters_to_yml():
            try:
                #self.process = subprocess.Popen(["./mediamtx"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.process = subprocess.Popen([mediamtx_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)                
                self.lbl_status.config(text="ESTADO: CONECTADO (Transmitiendo en Vivo)", fg="#2E7D32")
                self.status_card.config(bg="#E8F5E9")
                self.lbl_status.config(bg="#E8F5E9")
                self.btn_start.config(state=tk.DISABLED)
                self.btn_stop.config(state=tk.NORMAL)
            except Exception as e:
                messagebox.showerror("Error de Inicio", f"No se pudo iniciar ./mediamtx: {e}")

    def disconnect_cameras(self):
        if self.process:
            try:
                os.kill(self.process.pid, signal.SIGTERM)
                self.process.wait()
            except:
                pass
            self.process = None
        self.lbl_status.config(text="ESTADO: DESCONECTADO (Cámaras Apagadas)", fg="#C62828")
        self.status_card.config(bg="#FFEBEE")
        self.lbl_status.config(bg="#FFEBEE")
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = MediaMtxManager(root)
    
    def on_closing():
        app.disconnect_cameras()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
