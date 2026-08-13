#BLOQUE 1. LIBRERIAS Y CONFIGURACION DE CAMARA
import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
import pyrealsense2 as rs
from PIL import Image, ImageTk
import json
import paho.mqtt.client as mqtt
import threading

class AppRealSense:
    def __init__(self, root):
        self.root = root
        self.root.title("Segmentar RealSense")
        self.root.geometry("900x900")
        
        self.res_ancho_baja=160#120
        self.res_alto_baja=120#80#
        self.numero_voxels_max=1000#1000

        # 1. Configuración de Hardware Intel RealSense
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 15)
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 15)

        self.profile = self.pipeline.start(self.config)
        self.depth_scale = self.profile.get_device().first_depth_sensor().get_depth_scale()
        self.align = rs.align(rs.stream.color)

        # Extraer parámetros intrínsecos del lente activo
        color_stream = self.profile.get_stream(rs.stream.color).as_video_stream_profile()
        intr = color_stream.get_intrinsics()
        self.mtx = np.array([[intr.fx, 0, intr.ppx], [0, intr.fy, intr.ppy], [0, 0, 1]], dtype=np.float32)
        self.dist = np.array(intr.coeffs, dtype=np.float32)

        # Configuración del Detector ArUco Inclinado
        self.rvec_guardado = None
        self.tvec_guardado = None
        self.pose_aruco_guardada = None
        # Factor de suavizado (0.0 = máxima filtración/retraso, 1.0 = sin filtro)
        self.alpha = 0.1
        
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        aruco_params = cv2.aruco.DetectorParameters()
        aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector_aruco = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

        self.L = 0.05  # Tamaño real del ArUco físico en metros (5 cm)
        self.obj_pts = np.array([[-self.L / 2, self.L / 2, 0], [self.L / 2, self.L / 2, 0],
                                 [self.L / 2, -self.L / 2, 0], [-self.L / 2, -self.L / 2, 0]], dtype=np.float32)

        # 3. Construcción de Contenedores Gráficos de Tkinter
        self.f_izq = ttk.Frame(self.root, padding=10);
        self.f_izq.pack(side=tk.LEFT, fill=tk.Y)
        self.f_der = ttk.Frame(self.root, padding=10);
        self.f_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # =========================================================================
        # NUEVA DISTRIBUCIÓN GRÁFICA CORREGIDA (Imágenes grandes verticales / Zoom derecha)
        # =========================================================================
        # Imagen Original: Fila 0, Columna 0 (Arriba a la izquierda)
        self.lbl_orig = ttk.Label(self.f_der)
        self.lbl_orig.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # Imagen Filtrada por Color: Fila 1, Columna 0 (Abajo a la izquierda, justo debajo de la original)
        self.lbl_filt = ttk.Label(self.f_der)
        self.lbl_filt.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        ## Valores del bounding box (ejemplo: un cubo de 40x40x40 cm)
        self.bbox_x_min = -35.0
        self.bbox_x_max = 0.0
        self.bbox_y_min = -4.7
        self.bbox_y_max =10.0
        self.bbox_z_min = 0.0
        self.bbox_z_max = 35.0
        
        self.crear_sliders()

        # Inicializar variables de estado de memoria
        self.resp_img_baja = None
        self.resp_mask_baja = None
        self.resp_depth = None
        self.resp_rvec = None
        self.resp_tvec = None

        self.bucle()

        # Coloca esto en el __init__ de tu aplicación principal
        self.cliente_mqtt = None
        self.mqtt_activo = False  # Controla si el usuario presionó el botón de activar


    def crear_sliders(self):
        # 1. Contenedor general para los Sliders de Profundidad
        frame_prof = ttk.LabelFrame(self.f_izq, text=" PROFUNDIDAD (cm) ", padding=0)
        frame_prof.pack(fill=tk.X, pady=0)

        self.sld_dmin = tk.Scale(frame_prof, from_=0, to=300, orient=tk.HORIZONTAL)
        self.sld_dmin.set(20)
        self.sld_dmin.pack(fill=tk.X, pady=0)

        self.sld_dmax = tk.Scale(frame_prof, from_=0, to=300, orient=tk.HORIZONTAL)
        self.sld_dmax.set(80)
        self.sld_dmax.pack(fill=tk.X, pady=0)

        # =========================================================================
        # NUEVO: CREAR UN CONTENEDOR EN FILAS Y COLUMNAS PARA LOS COLORES HSV
        # =========================================================================
        frame_colores_grid = ttk.Frame(self.f_izq)
        frame_colores_grid.pack(fill=tk.X, pady=1)

        # --- COLUMNA 1: CONTROLES DEL OBJETO 1 (Azul) ---
        col1_frame = ttk.LabelFrame(frame_colores_grid, text=" COLOR HSV 1 ", padding=5)
        col1_frame.grid(row=0, column=0, padx=5, sticky="nsew")

        self.sld_hb = tk.Scale(col1_frame, from_=0, to=180, orient=tk.HORIZONTAL );
        self.sld_hb.set(0);
        self.sld_hb.pack(fill=tk.X)
        self.sld_ha = tk.Scale(col1_frame, from_=0, to=180, orient=tk.HORIZONTAL);
        self.sld_ha.set(148);
        self.sld_ha.pack(fill=tk.X)
        self.sld_sb = tk.Scale(col1_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_sb.set(0);
        self.sld_sb.pack(fill=tk.X)
        self.sld_sa = tk.Scale(col1_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_sa.set(255);
        self.sld_sa.pack(fill=tk.X)
        self.sld_vb = tk.Scale(col1_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_vb.set(0);
        self.sld_vb.pack(fill=tk.X)
        self.sld_va = tk.Scale(col1_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_va.set(255);
        self.sld_va.pack(fill=tk.X)

        # --- COLUMNA 2: CONTROLES DEL OBJETO 2 (Amarillo) ---
        col2_frame = ttk.LabelFrame(frame_colores_grid, text=" COLOR HSV 2 ", padding=5)
        col2_frame.grid(row=0, column=1, padx=5, sticky="nsew")

        self.sld_hb2 = tk.Scale(col2_frame, from_=0, to=180, orient=tk.HORIZONTAL);
        self.sld_hb2.set(180);
        self.sld_hb2.pack(fill=tk.X)
        self.sld_ha2 = tk.Scale(col2_frame, from_=0, to=180, orient=tk.HORIZONTAL);
        self.sld_ha2.set(180);
        self.sld_ha2.pack(fill=tk.X)
        self.sld_sb2 = tk.Scale(col2_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_sb2.set(255);
        self.sld_sb2.pack(fill=tk.X)
        self.sld_sa2 = tk.Scale(col2_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_sa2.set(255);
        self.sld_sa2.pack(fill=tk.X)
        self.sld_vb2 = tk.Scale(col2_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_vb2.set(255);
        self.sld_vb2.pack(fill=tk.X)
        self.sld_va2 = tk.Scale(col2_frame, from_=0, to=255, orient=tk.HORIZONTAL);
        self.sld_va2.set(255);
        self.sld_va2.pack(fill=tk.X)

        #==================================================
        # --- CONTENEDOR PARA EL BOUNDING BOX, RESOLUCION Y PIXELES ---
        #==================================================
        frame_bbox = ttk.LabelFrame(self.f_izq, text=" Volumen de Interés (BBox en cm) ")
        # Ajusta el empaquetado (pack o grid) según el diseño actual de tu interfaz
        frame_bbox.pack(padx=1, pady=1, fill="x") 

        # Configuración de columnas para que se vea ordenado
        frame_bbox.columnconfigure((0, 1, 2, 3), weight=1, pad=1)

        # --- CAMPOS PARA X ---
        ttk.Label(frame_bbox, text="X Min:").grid(row=0, column=0, sticky="e")
        self.ent_x_min = ttk.Entry(frame_bbox, width=8)
        self.ent_x_min.insert(0, str(self.bbox_x_min))
        self.ent_x_min.grid(row=0, column=1, pady=1, sticky="w")

        ttk.Label(frame_bbox, text="X Max:").grid(row=0, column=2, sticky="e")
        self.ent_x_max = ttk.Entry(frame_bbox, width=8)
        self.ent_x_max.insert(0, str(self.bbox_x_max))
        self.ent_x_max.grid(row=0, column=3, pady=1, sticky="w")

        # --- CAMPOS PARA Y ---
        ttk.Label(frame_bbox, text="Y Min:").grid(row=1, column=0, sticky="e")
        self.ent_y_min = ttk.Entry(frame_bbox, width=8)
        self.ent_y_min.insert(0, str(self.bbox_y_min))
        self.ent_y_min.grid(row=1, column=1, pady=1, sticky="w")

        ttk.Label(frame_bbox, text="Y Max:").grid(row=1, column=2, sticky="e")
        self.ent_y_max = ttk.Entry(frame_bbox, width=8)
        self.ent_y_max.insert(0, str(self.bbox_y_max))
        self.ent_y_max.grid(row=1, column=3, pady=1, sticky="w")

        # --- CAMPOS PARA Z ---
        ttk.Label(frame_bbox, text="Z Min:").grid(row=2, column=0, sticky="e")
        self.ent_z_min = ttk.Entry(frame_bbox, width=8)
        self.ent_z_min.insert(0, str(self.bbox_z_min))
        self.ent_z_min.grid(row=2, column=1, pady=1, sticky="w")

        ttk.Label(frame_bbox, text="Z Max:").grid(row=2, column=2, sticky="e")
        self.ent_z_max = ttk.Entry(frame_bbox, width=8)
        self.ent_z_max.insert(0, str(self.bbox_z_max))
        self.ent_z_max.grid(row=2, column=3, pady=1, sticky="w")

        frame_bbox = ttk.LabelFrame(self.f_izq, text=" Resolución y voxels ")
        # Ajusta el empaquetado (pack o grid) según el diseño actual de tu interfaz
        frame_bbox.pack(padx=1, pady=1, fill="x")
        
        #---------CAMPOS PARA RESOLUCION DE PROCESAMIENTO Y VOXELS--------        
        ttk.Label(frame_bbox, text="Res Pro Ancho:").grid(row=0, column=0, sticky="e")
        self.ent_res_ancho = ttk.Entry(frame_bbox, width=8)
        self.ent_res_ancho.insert(0, str(self.res_ancho_baja))
        self.ent_res_ancho.grid(row=0, column=1, pady=1, sticky="w")
        
        ttk.Label(frame_bbox, text="Res Pro Alto:").grid(row=0, column=2, sticky="e")
        self.ent_res_alto = ttk.Entry(frame_bbox, width=8)
        self.ent_res_alto.insert(0, str(self.res_alto_baja))
        self.ent_res_alto.grid(row=0, column=3, pady=1, sticky="w")
        
        ttk.Label(frame_bbox, text="Numero de Voxels:").grid(row=1, column=0, sticky="e")
        self.ent_voxels = ttk.Entry(frame_bbox, width=8)
        self.ent_voxels.insert(0, str(self.numero_voxels_max))
        self.ent_voxels.grid(row=1, column=1, pady=1, sticky="w")
        
        # --- BOTÓN PARA ACTUALIZAR VALORES ---
        self.btn_aplicar_bbox = ttk.Button(frame_bbox, text="Actualizar Valores", command=self.actualizar_valores_bbox)
        self.btn_aplicar_bbox.grid(row=2, column=0, columnspan=4, pady=1)
        
        #==================================================
        #  Contenedor general para el Servidor MQTT
        #==================================================
        frame_mqtt = ttk.LabelFrame(self.f_izq, text=" SERVIDOR HIVEMQ (MQTT) ", padding=0)
        frame_mqtt.pack(fill=tk.X, pady=0)

        ttk.Label(frame_mqtt, text="URL del Bróker:").pack(anchor=tk.W)
        self.ent_url = ttk.Entry(frame_mqtt);
        self.ent_url.insert(0, "0319358e340a4537960aa39a9b9b32cc.s1.eu.hivemq.cloud");
        self.ent_url.pack(fill=tk.X, pady=0)

        ttk.Label(frame_mqtt, text="Puerto:").pack(anchor=tk.W)
        self.ent_port = ttk.Entry(frame_mqtt);
        self.ent_port.insert(0, "8883");
        self.ent_port.pack(fill=tk.X, pady=0)

        ttk.Label(frame_mqtt, text="Usuario:").pack(anchor=tk.W)
        self.ent_user = ttk.Entry(frame_mqtt);
        self.ent_user.insert(0, "Automatica_Lab");
        self.ent_user.pack(fill=tk.X, pady=0)

        # Campos de credenciales del Servidor MQTT (Conserva tus Entries)
        ttk.Label(frame_mqtt, text="Contraseña:").pack(anchor=tk.W)
        self.ent_pass = ttk.Entry(frame_mqtt, show="*");
        self.ent_pass.insert(0, "aLab0123456789");
        self.ent_pass.pack(fill=tk.X, pady=0)

        # =========================================================================
        # NUEVO: BOTÓN DE CONEXIÓN SEGURA Y BOTONES DE ACCIÓN
        # =========================================================================
        self.btn_conectar = ttk.Button(self.f_izq, text="Conectar Servidor MQTT", command=self.gestionar_conexion_mqtt)
        self.btn_conectar.pack(fill=tk.X, pady=(5, 0))

        # Deshabilitamos temporalmente el botón de envío manual hasta que se conecte el servidor
        self.btn_imprimir = ttk.Button(self.f_izq, text="Enviar Voxels",
                                       command=self.ejecutar_envio_mqtt_global, state=tk.DISABLED)
        self.btn_imprimir.pack(fill=tk.X, pady=0)

        ttk.Button(self.f_izq, text="Cerrar Programa", command=self.salir).pack(fill=tk.X, pady=0)
        

    def actualizar_valores_bbox(self):
        try:
            self.bbox_x_min = float(self.ent_x_min.get().strip())
            self.bbox_x_max = float(self.ent_x_max.get().strip())
            self.bbox_y_min = float(self.ent_y_min.get().strip())
            self.bbox_y_max = float(self.ent_y_max.get().strip())
            self.bbox_z_min = float(self.ent_z_min.get().strip())
            self.bbox_z_max = float(self.ent_z_max.get().strip())
            print(f">>> BBox Actualizado -> X:[{self.bbox_x_min}, {self.bbox_x_max}] | Y:[{self.bbox_y_min}, {self.bbox_y_max}] | Z:[{self.bbox_z_min}, {self.bbox_z_max}]")
            
            self.res_ancho_baja=int(self.ent_res_ancho.get().strip())
            self.res_alto_baja=int(self.ent_res_alto.get().strip())
            self.numero_voxels_max=int(self.ent_voxels.get().strip())
            print(f">>> Resolucion de procesamiento actualizada: [{self.res_ancho_baja}, {self.res_alto_baja}] | Numero de voxels: {self.numero_voxels_max}")
            
        except ValueError:
            print(">>> ERROR: Asegúrate de ingresar solo números válidos en los campos del BBox.")

    def dibujar_bbox_3d(self, img_orig, rvec, tvec):
        # 1. Creamos los 8 vértices del cubo en el espacio 3D (en metros) basados en tus sliders
        # Convertimos de cm (sliders) a metros dividiendo entre 100
        x_min, x_max = self.bbox_x_min / 100.0, self.bbox_x_max / 100.0
        y_min, y_max = self.bbox_y_min / 100.0, self.bbox_y_max / 100.0
        z_min, z_max = self.bbox_z_min / 100.0, self.bbox_z_max / 100.0
        # Definición de las 8 esquinas del cubo en 3D relativo al ArUco
        pts_3d = np.array([
            [x_min, y_min, z_min], [x_max, y_min, z_min], [x_max, y_max, z_min], [x_min, y_max, z_min], # Base inferior
            [x_min, y_min, z_max], [x_max, y_min, z_max], [x_max, y_max, z_max], [x_min, y_max, z_max]  # Base superior
        ], dtype=np.float32)
        # 2. Proyectamos los puntos 3D a coordenadas de píxeles 2D utilizando la calibración de tu cámara
        pts_2d, _ = cv2.projectPoints(pts_3d, rvec, tvec, self.mtx, self.dist)
        pts_2d = pts_2d.reshape(-1, 2).astype(int)
        # 3. Dibujamos las aristas del cubo sobre la imagen original
        # Definimos el color en BGR (ej: Verde = (0, 255, 0)) y grosor de línea 2
        color = (0, 255, 0)         
        # Unimos las 4 líneas de la base inferior
        for i in range(4):
            cv2.line(img_orig, tuple(pts_2d[i]), tuple(pts_2d[(i + 1) % 4]), color, 2)            
        # Unimos las 4 líneas de la base superior
        for i in range(4):
            cv2.line(img_orig, tuple(pts_2d[i + 4]), tuple(pts_2d[((i + 1) % 4) + 4]), color, 2)            
        # Unimos las 4 columnas verticales que conectan la base inferior con la superior
        for i in range(4):
            cv2.line(img_orig, tuple(pts_2d[i]), tuple(pts_2d[i + 4]), color, 2)


    #Bloque 2. Seccion A
    def calcular_mapa_relativo_aruco(self, img_baja, mascara_baja, depth_alta, rvec, tvec):
        lista_puntos_3d = []
        R_directa, _ = cv2.Rodrigues(rvec)
        R_inversa = R_directa.T
        alto_baja, ancho_baja = self.res_alto_baja, self.res_ancho_baja
        fx, fy = float(self.mtx[0][0]), float(self.mtx[1][1])
        ppx, ppy = float(self.mtx[0][2]), float(self.mtx[1][2])

        for v in range(alto_baja):
            for u in range(ancho_baja):
                if mascara_baja[v, u] != 255: continue
                u_alta = min(max(int(u * (640 / ancho_baja)), 0), 639)
                v_alta = min(max(int(v * (480 / alto_baja)), 0), 479)
                z_cam = depth_alta[v_alta, u_alta]
                if z_cam <= 0: continue

                x_cam = (u_alta - ppx) * z_cam / fx
                y_cam = (v_alta - ppy) * z_cam / fy
                P_cam = np.array([[x_cam], [y_cam], [z_cam]], dtype=np.float32)

                P_aruco = np.dot(R_inversa, (P_cam - tvec))
                b, g, r = img_baja[v, u]
                #Las coordenadas de voxels en mm como int
                if (P_aruco[0][0]*100 > self.bbox_x_min) and (P_aruco[0][0]*100 < self.bbox_x_max) and (P_aruco[1][0]*100 > self.bbox_y_min) and (P_aruco[1][0]*100 < self.bbox_y_max) and (P_aruco[2][0]*100 > self.bbox_z_min) and (P_aruco[2][0]*100 < self.bbox_z_max):
                    lista_puntos_3d.append(
                        [int(float(P_aruco[0][0])*1000), int(float(P_aruco[1][0])*1000), int(float(P_aruco[2][0])*1000), int(r), int(g), int(b)])
        return lista_puntos_3d


    def procesar_color_y_aruco(self, img_orig, img_prof, depth_m, bajo_c, alto_c, bajo_c2, alto_c2):                
        #Deteccion de ARUCO
        gray = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
        esquinas, ids, _ = self.detector_aruco.detectMarkers(gray)
        encontrado_ahora = False

        if ids is not None:
            for i in range(len(ids)):
                if ids[i] == 0:
                    cv2.aruco.drawDetectedMarkers(img_orig, [esquinas[i]], np.array([]))
                    pts_img = esquinas[i].astype(np.float32).reshape(4, 2)
                    _, rvec, tvec = cv2.solvePnP(self.obj_pts, pts_img, self.mtx, self.dist,
                                                 flags=cv2.SOLVEPNP_IPPE_SQUARE)
                    
                    # Formateamos la pose actual detectada
                    pose_actual = (float(tvec[0][0]) * 100, float(tvec[1][0]) * 100, float(tvec[2][0]) * 100)

                    # Si es la primera detección, inicializamos directamente los valores
                    if self.rvec_guardado is not None:
                        # Aplicamos el filtro de media móvil exponencial
                        self.rvec_guardado = self.alpha * rvec + (1 - self.alpha) * self.rvec_guardado
                        self.tvec_guardado = self.alpha * tvec + (1 - self.alpha) * self.tvec_guardado
                        self.pose_aruco_guardada = (self.alpha * pose_actual[0] + (1 - self.alpha) * self.pose_aruco_guardada[0],self.alpha * pose_actual[1] + (1 - self.alpha) * self.pose_aruco_guardada[1],self.alpha * pose_actual[2] + (1 - self.alpha) * self.pose_aruco_guardada[2])                        
        
                    else:
                        # Primera iteración válida sin datos previos
                        self.rvec_guardado = rvec
                        self.tvec_guardado = tvec
                        self.pose_aruco_guardada = pose_actual

                    encontrado_ahora = True
                    break

        # Si tenemos datos (ya sean nuevos filtrados o históricos), dibujamos los ejes estables
        if self.rvec_guardado is not None:
            cv2.drawFrameAxes(img_orig, self.mtx, self.dist, self.rvec_guardado, self.tvec_guardado, self.L * 0.8, 3)
            # --- NUEVA LÍNEA: Dibujamos el volumen 3D dinámico ---
            self.dibujar_bbox_3d(img_orig, self.rvec_guardado, self.tvec_guardado)
        
        # Variables limpias listas para el siguiente procesamiento
        rvec_guardado = self.rvec_guardado
        tvec_guardado = self.tvec_guardado
        pose_aruco = self.pose_aruco_guardada

        #Filtrado de imagen
        suavizada = cv2.GaussianBlur(img_prof, (5, 5), 0)
        hsv = cv2.cvtColor(suavizada, cv2.COLOR_BGR2HSV)
        kernel = np.ones((5, 5), np.uint8)
        ancho_baja, alto_baja = self.res_ancho_baja, self.res_alto_baja        
        img_baja = cv2.resize(img_prof, (ancho_baja, alto_baja), interpolation=cv2.INTER_LINEAR)

        # Canal Objeto 1 
        mask1 = cv2.morphologyEx(
            cv2.morphologyEx(cv2.inRange(hsv, bajo_c, alto_c), cv2.MORPH_CLOSE, kernel, iterations=2), cv2.MORPH_OPEN,
            kernel, iterations=1)
        mask_b1 = cv2.resize(mask1, (ancho_baja, alto_baja), interpolation=cv2.INTER_NEAREST)
        cont1, _ = cv2.findContours(mask_b1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        m_fb1, bbox1 = np.zeros_like(mask_b1), None
        if cont1:
            c_max = max(cont1, key=cv2.contourArea)
            if cv2.contourArea(c_max) > 10:
                cv2.drawContours(m_fb1, [c_max], -1, 255, -1); bbox1 = cv2.boundingRect(c_max)
                #print(f"Area objeto 1:{cv2.contourArea(c_max)}")

        # Canal Objeto 2 
        mask2 = cv2.morphologyEx(
            cv2.morphologyEx(cv2.inRange(hsv, bajo_c2, alto_c2), cv2.MORPH_CLOSE, kernel, iterations=2), cv2.MORPH_OPEN,
            kernel, iterations=1)
        mask_b2 = cv2.resize(mask2, (ancho_baja, alto_baja), interpolation=cv2.INTER_NEAREST)
        cont2, _ = cv2.findContours(mask_b2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        m_fb2, bbox2 = np.zeros_like(mask_b2), None
        if cont2:
            c_max = max(cont2, key=cv2.contourArea)
            if cv2.contourArea(c_max) > 10:
                cv2.drawContours(m_fb2, [c_max], -1, 255, -1); bbox2 = cv2.boundingRect(c_max)
                #print(f"Area objeto 2:{cv2.contourArea(c_max)}")

        mask_final_baja = cv2.bitwise_or(m_fb1, m_fb2)
        return mask_final_baja, (bbox1, bbox2), img_baja, pose_aruco, rvec_guardado, tvec_guardado


    def bucle(self):
        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=80)
            aligned = self.align.process(frames)
            c_frame, d_frame = aligned.get_color_frame(), aligned.get_depth_frame()

            if c_frame and d_frame:
                img = np.asanyarray(c_frame.get_data()).copy()
                depth = np.asanyarray(d_frame.get_data()) * self.depth_scale
                ho, wo = img.shape[:2]

                intr = c_frame.get_profile().as_video_stream_profile().get_intrinsics()
                self.mtx = np.array([[intr.fx, 0, intr.ppx], [0, intr.fy, intr.ppy], [0, 0, 1]], dtype=np.float32)
                self.dist = np.array(intr.coeffs, dtype=np.float32)

                dm_in, dm_ax = self.sld_dmin.get() / 100.0, self.sld_dmax.get() / 100.0
                b_c = np.array([self.sld_hb.get(), self.sld_sb.get(), self.sld_vb.get()])
                a_c = np.array([self.sld_ha.get(), self.sld_sa.get(), self.sld_va.get()])
                b_c2 = np.array([self.sld_hb2.get(), self.sld_sb2.get(), self.sld_vb2.get()])
                a_c2 = np.array([self.sld_ha2.get(), self.sld_sa2.get(), self.sld_va2.get()])

                mask_p = ((depth >= dm_in) & (depth <= dm_ax)).astype(np.uint8) * 255
                img_seg_p = cv2.bitwise_and(img, img, mask=mask_p)

                m_baja, b_baja, img_b, p_aruco, rvec_g, tvec_g = self.procesar_color_y_aruco(img, img_seg_p, depth, b_c,
                                                                                             a_c, b_c2, a_c2)
                self.resp_img_baja, self.resp_mask_baja, self.resp_depth = img_b.copy(), m_baja.copy(), depth.copy()
                self.resp_rvec, self.resp_tvec = rvec_g, tvec_g

                m_alta = cv2.resize(m_baja, (wo, ho), interpolation=cv2.INTER_NEAREST)
                res_final = cv2.bitwise_and(img_seg_p, img_seg_p, mask=m_alta)

                bbox1, bbox2 = b_baja
                if bbox1:
                    x1, y1 = int(bbox1[0] * (wo / self.res_ancho_baja)), int(bbox1[1] * (ho / self.res_alto_baja))
                    w1, h1 = int(bbox1[2] * (wo / self.res_ancho_baja)), int(bbox1[3] * (ho / self.res_alto_baja))
                    cv2.rectangle(img, (x1, y1), (x1 + w1, y1 + h1), (0, 165, 255), 2)
                    cv2.putText(img, "OBJ 1", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)
                if bbox2:
                    x2, y2 = int(bbox2[0] * (wo / self.res_ancho_baja)), int(bbox2[1] * (ho / self.res_alto_baja))
                    w2, h2 = int(bbox2[2] * (wo / self.res_ancho_baja)), int(bbox2[3] * (ho / self.res_alto_baja))
                    cv2.rectangle(img, (x2, y2), (x2 + w2, y2 + h2), (0, 255, 0), 2)
                    cv2.putText(img, "OBJ 2", (x2, y2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                if p_aruco is not None:
                    cv2.putText(img, f"ArUco XYZ: [{p_aruco[0]:.1f}, {p_aruco[1]:.1f}, {p_aruco[2]:.1f}] cm", (15, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

                im_o = ImageTk.PhotoImage(
                    image=Image.fromarray(cv2.cvtColor(cv2.resize(img, (480, 360)), cv2.COLOR_BGR2RGB)))
                im_f = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(cv2.resize(res_final, (480, 360)), cv2.COLOR_BGR2RGB)))

                self.lbl_orig.configure(image=im_o);
                self.lbl_orig.image = im_o
                self.lbl_filt.configure(image=im_f);
                self.lbl_filt.image = im_f
                self.root.update_idletasks()
        except Exception as e:
            print(f"Error bucle: {e}")
        self.root.after(66, self.bucle)

    # Esta es la lógica que debe ejecutar tu hilo cuando el usuario interactúa con el botón   
    def gestionar_conexion_mqtt(self):
    
        # --- SUB-FUNCIÓN CALLBACK: Se ejecuta automáticamente al recibir un mensaje ---
        def al_recibir_mensaje(client, userdata, message):
            try:
                topico = message.topic
                # Decodificamos el payload de bytes a texto
                payload_str = message.payload.decode("utf-8").strip()
                print(f">>> MQTT RECIBCIDO - Tópico: {topico} | Mensaje: {payload_str}")
                
                if topico == "voxelsTrigger":
                    # Evaluamos si el mensaje es un booleano True o el texto "true" / "True"
                    es_verdadero = False
                    if payload_str.lower() == "true":
                        es_verdadero = True
                    else:
                        try:
                            # Por si viene en formato JSON válido (ej: true)
                            es_verdadero = bool(json.loads(payload_str))
                        except:
                            pass
                    
                    if es_verdadero:
                        print(">>> MQTT: ¡voxelsTrigger es True! Disparando acción remota...")
                        
                        # 1. Ejecutamos la acción equivalente al botón de imprimir
                        # (Llamamos al método que tengas asignado a tu boton_imprimir)
                        if hasattr(self, 'ejecutar_envio_mqtt_global'):
                            # Se recomienda ejecutarlo en un hilo rápido para no bloquear el bucle de MQTT
                            threading.Thread(target=self.ejecutar_envio_mqtt_global, daemon=True).start()
                        else:
                            print(">>> MQTT ADVERTENCIA: No se encontró el método ejecutar_envio_mqtt_global")
                        
                        # 2. Apagamos el trigger de inmediato enviando un False de regreso a HiveMQ
                        # Usamos qos=1 para asegurar que el servidor reciba la confirmación del cambio de estado
                        client.publish("voxelsTrigger", "false", qos=1, retain=True)
                        print(">>> MQTT: voxelsTrigger reseteado a False en el servidor.")
                        
            except Exception as e:
                print(f">>> MQTT ERROR EN CALLBACK: {e}")

        # --- LÓGICA PRINCIPAL DE CONEXIÓN DE FONDO ---
        def proceso_conectar_fondo():
            try:
                snap = {
                    "url": self.ent_url.get().strip(),
                    "port": int(self.ent_port.get().strip()),
                    "user": self.ent_user.get().strip(),
                    "pass": self.ent_pass.get().strip()
                }
                
                if self.cliente_mqtt is not None:
                    return 
                    
                try: 
                    self.cliente_mqtt = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
                    # Asignamos el callback para la API versión 2
                    self.cliente_mqtt.on_message = al_recibir_mensaje
                except AttributeError: 
                    self.cliente_mqtt = mqtt.Client()
                    # Asignamos el callback para versiones antiguas de paho-mqtt
                    self.cliente_mqtt.on_message = lambda client, userdata, msg: al_recibir_mensaje(client, userdata, msg)
                
                if snap["user"] and snap["pass"]: self.cliente_mqtt.username_pw_set(snap["user"], snap["pass"])
                if snap["port"] == 8883: self.cliente_mqtt.tls_set()
                
                self.cliente_mqtt.connect(snap["url"], snap["port"], keepalive=60)
                self.cliente_mqtt.loop_start() 
                
                # --- NUEVA LÍNEA: Suscribirse al tópico del Trigger ---
                # Nos suscribimos con QoS 1 para asegurar que no se pierdan peticiones remotas
                self.cliente_mqtt.subscribe("voxelsTrigger", qos=1)
                
                self.mqtt_activo = True
                print(">>> MQTT: Comunicación ACTIVADA y suscrito a 'voxelsTrigger'.")
                self.btn_conectar.config(text = "Desconectar Servidor MQTT")              
                
                # Intentar habilitar botón de acuerdo a tu librería de interfaz
                try: self.btn_imprimir.config(state="normal")
                except: self.btn_imprimir.setEnabled(True)
                
            except Exception as e:
                print(f">>> MQTT ERROR AL ACTIVAR: {e}")
                self.mqtt_activo = False

        if not self.mqtt_activo:
            print(">>> MQTT: Iniciando hilo de conexión...")
            hilo_conexion = threading.Thread(target=proceso_conectar_fondo, daemon=True)
            hilo_conexion.start()
        else:
            self.mqtt_activo = False
            if self.cliente_mqtt is not None:
                self.cliente_mqtt.loop_stop()
                self.cliente_mqtt.disconnect()
                self.cliente_mqtt = None
            print(">>> MQTT: Comunicación DESACTIVADA por el usuario.")
            self.btn_conectar.config(text = "Conectar Servidor MQTT")
            
            try: self.btn_imprimir.config(state="disabled")
            except: self.btn_imprimir.setEnabled(False)




    def ejecutar_envio_mqtt_global(self):
        try:
            lista_puntos_3d = self.calcular_mapa_relativo_aruco(self.resp_img_baja, self.resp_mask_baja, self.resp_depth, self.resp_rvec, self.resp_tvec)
 
            # Si la comunicación está apagada por el usuario, no hacemos nada más
            if not self.mqtt_activo or self.cliente_mqtt is None:
                return

            print(f"\n=======================================================\n--- ENVIANDO ({len(lista_puntos_3d)}) VOXELS A HIVEMQ ---\n=======================================================")
            if len(lista_puntos_3d) == 0: return
            if (len(lista_puntos_3d) > self.numero_voxels_max):
                print(f"Hay {len(lista_puntos_3d)} voxels detectados, se enviaran los primeros {self.numero_voxels_max}")
            payload_json = json.dumps({"puntos": lista_puntos_3d[0:int(self.numero_voxels_max)]})

            # Publicación directa e instantánea sin bloqueos
            self.cliente_mqtt.publish("voxels", payload_json, qos=0)
            print(">>> MQTT: Mensaje enviado de fondo.")

        except Exception as error_red: 
            print(f">>> MQTT ERROR EN FUNCIÓN: {error_red}")


    def salir(self):
        # --- NUEVO: Desconectar cliente de escucha de forma limpia ---
        if hasattr(self, 'cliente_trigger'):
            try:
                self.cliente_trigger.disconnect()
            except:
                pass

        self.pipeline.stop()
        self.root.quit()


if __name__ == "__main__":
    ventana = tk.Tk()
    app = AppRealSense(ventana)
    ventana.protocol("WM_DELETE_WINDOW", app.salir); ventana.mainloop()
