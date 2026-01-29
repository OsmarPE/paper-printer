import os
import subprocess
from flask import Flask, request, send_file, jsonify, render_template,send_from_directory
from werkzeug.utils import secure_filename
from fpdf import FPDF
from PIL import Image
import win32print
import win32api
import time

app = Flask(__name__)

# CONFIGURACIÓN
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DOWNLOADS_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

# RUTA LIBREOFFICE (Ajustar según tu PC)
LIBREOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"
def crear_pdf_imagenes(rutas_imagenes, layout, position): # <--- Recibe 'position'
    # Dimensiones Hoja Carta en mm
    PAGE_W = 215.9
    PAGE_H = 279.4
    MARGIN = 10
    
    pdf = FPDF('P', 'mm', 'Letter')
    pdf.set_auto_page_break(auto=False)

    for img_path in rutas_imagenes:
        pdf.add_page()

        with Image.open(img_path) as img:
            img_w_px, img_h_px = img.size
            aspect_ratio = img_w_px / img_h_px

        # --- 1. CALCULAR TAMAÑO (Igual que antes) ---
        if layout == 'id_card':
            target_w, target_h = 86, 54
            final_w, final_h = target_w, target_h
            
        elif layout == 'half':
            max_w = PAGE_W - (MARGIN * 2)
            max_h = (PAGE_H / 2) - (MARGIN * 2)
            if max_w / max_h > aspect_ratio:
                final_h = max_h
                final_w = max_h * aspect_ratio
            else:
                final_w = max_w
                final_h = max_w / aspect_ratio
                
        else: # full
            max_w = PAGE_W - (MARGIN * 2)
            max_h = PAGE_H - (MARGIN * 2)
            if max_w / max_h > aspect_ratio:
                final_h = max_h
                final_w = max_h * aspect_ratio
            else:
                final_w = max_w
                final_h = max_w / aspect_ratio

        # --- 2. CALCULAR POSICIÓN (La Nueva Lógica) ---
        
        # Eje X: Siempre centrado horizontalmente
        pos_x = (PAGE_W - final_w) / 2

        # Eje Y: Depende de lo que elija el usuario
        if position == 'top':
            # Pegado al margen superior
            pos_y = MARGIN
            
        elif position == 'bottom':
            # Altura total - Altura imagen - Margen
            pos_y = PAGE_H - final_h - MARGIN
            
        else: # 'center' (Default)
            # La fórmula de centrado vertical
            pos_y = (PAGE_H - final_h) / 2

        # --- 3. ESTAMPAR IMAGEN ---
        pdf.image(img_path, x=pos_x, y=pos_y, w=final_w, h=final_h)

    ruta_pdf = os.path.join(UPLOAD_FOLDER, "salida_personalizada.pdf")
    pdf.output(ruta_pdf)
    return ruta_pdf

def convertir_doc_libreoffice(ruta_doc):
    """Usa LibreOffice en modo headless para docs complejos"""
    comando = [
        LIBREOFFICE_PATH, '--headless', '--convert-to', 'pdf',
        '--outdir', UPLOAD_FOLDER, ruta_doc
    ]
    subprocess.run(comando, check=True)
    nombre_base = os.path.splitext(os.path.basename(ruta_doc))[0]
    return os.path.join(UPLOAD_FOLDER, f"{nombre_base}.pdf")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/img-to-pdf')
def image_to_pdf():
    return render_template('image-to-pdf.html')

@app.route('/api/convertir', methods=['POST'])
def api_convertir():
    # 1. Validaciones básicas
    if 'files[]' not in request.files:
        return jsonify({"error": "No hay archivos"}), 400
    
    files = request.files.getlist('files[]')
    layout = request.form.get('layout', 'full') # Default: Carta completa
    position = request.form.get('position', 'center') # <--- Capturamos la posición
    rutas_guardadas = []
    es_imagen = True
    
    # 2. Guardar archivos
    for f in files:
        print(f.filename)
        if f.filename == '': continue
        filename = secure_filename(f.filename)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)
        rutas_guardadas.append(path)
        
        # Detección simple: si uno no es imagen, cambiamos modo a LibreOffice
        ext = filename.split('.')[-1].lower()
        if ext not in ['jpg', 'jpeg', 'png', 'bmp', 'webp']:
            es_imagen = False

    if not rutas_guardadas:
        return jsonify({"error": "Archivos vacíos"}), 400

    try:
        ruta_final = ""
        
        # 3. Lógica de selección de motor
        if es_imagen:
            # Usamos nuestro motor FPDF con control de tamaño
            ruta_final = crear_pdf_imagenes(rutas_guardadas, layout, position)
        else:
            # Si hay documentos de Office, ignoramos el layout y usamos LibreOffice
            # (LibreOffice maneja sus propios tamaños de papel internos)
            ruta_final = convertir_doc_libreoffice(rutas_guardadas[0])

        # 4. Retornar el archivo binario
        return send_file(ruta_final, as_attachment=True, download_name=f"impresion_{files[0].filename}.pdf")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# RUTA A SUMATRA (Ajusta esto)
SUMATRA_PATH = os.path.join(os.getcwd(), "SumatraPDF.exe")

def obtener_impresoras():
    """Devuelve una lista de impresoras instaladas y su estado básico"""
    impresoras = []
    # Enumera impresoras locales y de red
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    
    for printer in win32print.EnumPrinters(flags):
        nombre = printer[2]
        # Obtenemos el handle para consultar estado
        try:
            hPrinter = win32print.OpenPrinter(nombre)
            info = win32print.GetPrinter(hPrinter, 2)
            
            # El estado es un bitmask (complejo), simplificamos:
            estado_code = info['Status']
            estado_txt = "ready" if estado_code == 0 else f"pending"
            
            # Contar trabajos en cola
            jobs = info['cJobs']
            
            impresoras.append({
                "nombre": nombre,
                "estado": estado_txt,
                "cola": jobs
            })
            win32print.ClosePrinter(hPrinter)
        except:
            continue
            
    return impresoras

def imprimir_silencioso(ruta_pdf, nombre_impresora):
    """Manda el PDF directo a la impresora usando SumatraPDF"""
    try:
        # Comando: SumatraPDF.exe -print-to "NombreImpresora" "archivo.pdf"
        comando = [
            SUMATRA_PATH,
            "-print-to", nombre_impresora,
            "-silent", # No abre ventana
            ruta_pdf
        ]
        subprocess.run(comando, check=True)
        return True
    except Exception as e:
        print(f"Error imprimiendo: {e}")
        return False

# --- NUEVAS RUTAS FLASK ---

@app.route('/prints')
def pagina_impresoras():
    # Muestra el panel de gestión
    lista = obtener_impresoras()
    return render_template('prints.html', impresoras=lista)

@app.route('/api/subir_y_imprimir', methods=['POST'])
def api_subir_y_imprimir():
    if 'file' not in request.files:
        return jsonify({"success": False, "msg": "No hay archivo"}), 400
    
    archivo = request.files['file']
    impresora = request.form.get('impresora')
    copias = request.form.get('copias', '1')
    rango = request.form.get('rango', '')
    
    # NUEVOS PARÁMETROS
    formato = request.form.get('formato', 'Letter') # Letter, Legal, A4
    modo_color = request.form.get('color', 'color') # color, monochrome

    if archivo.filename == '':
        return jsonify({"success": False, "msg": "Nombre vacío"}), 400

    filename = secure_filename(archivo.filename)
    ruta_pdf = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    archivo.save(ruta_pdf)
    
    # CONSTRUCCIÓN DE SETTINGS PARA SUMATRA
    # Sumatra usa comas para separar opciones: "2x,paper=Letter,color=monochrome"
    settings = []
    
    # 1. Copias
    settings.append(f"{copias}x")
    
    # 2. Rango de páginas
    if rango and rango.strip():
        settings.append(rango)
        
    # 3. Formato de Papel (Letter, Legal, A4, A3, Tabloid)
    # Nota: 'Legal' es el estándar para Oficio en la mayoría de drivers
    settings.append(f"paper={formato}")
    
    # 4. Modo de Color
    settings.append(f"color={modo_color}")

    # Unimos todo con comas
    settings_str = ",".join(settings)

    comando = [
        SUMATRA_PATH,
        "-print-to", impresora,
        "-print-settings", settings_str,
        "-silent",
        ruta_pdf
    ]
    
    print(f"Ejecutando: {comando}") # Para que veas en consola qué hace

    try:
        subprocess.run(comando, check=True)
        return jsonify({"success": True, "msg": "Enviado a imprimir correctamente"})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Error: {str(e)}"}), 500
@app.route('/api/imprimir_directo', methods=['POST'])
def api_imprimir_directo():
    data = request.json
    nombre_impresora = data.get('impresora')
    # Usamos el último archivo generado (o podrías pasar el nombre del archivo)
    # Para este ejemplo, asumimos que quieren imprimir el "salida_personalizada.pdf"
    archivo_a_imprimir = os.path.join(app.config['UPLOAD_FOLDER'], "salida_personalizada.pdf")
    
    if not os.path.exists(archivo_a_imprimir):
        return jsonify({"success": False, "msg": "No hay archivo reciente para imprimir"}), 404

    exito = imprimir_silencioso(archivo_a_imprimir, nombre_impresora)
    
    if exito:
        return jsonify({"success": True, "msg": f"Enviado a {nombre_impresora}"})
    else:
        return jsonify({"success": False, "msg": "Error al comunicar con la impresora"}), 500

def obtener_imagenes_recientes():
    """Devuelve lista de imágenes en Descargas ordenadas por fecha (más nuevas primero)"""
    archivos = []
    try:
        # Escanear directorio
        for entry in os.scandir(DOWNLOADS_FOLDER):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    # Guardamos nombre y fecha para ordenar
                    archivos.append({
                        "nombre": entry.name,
                        "fecha": entry.stat().st_mtime,
                        "fecha_legible": time.ctime(entry.stat().st_mtime)
                    })
        
        # Ordenar: Más nuevo al principio
        archivos.sort(key=lambda x: x['fecha'], reverse=True)
        return archivos
    except Exception as e:
        print(f"Error leyendo descargas: {e}")
        return []

# --- RUTAS NUEVAS ---

@app.route('/images')
def ver_descargas():
    imagenes = obtener_imagenes_recientes()
    return render_template('images.html', imagenes=imagenes)

# ESTA RUTA ES CRUCIAL: Permite al HTML mostrar las imágenes de Windows
@app.route('/cdn/descargas/<path:filename>')
def servir_imagen_descargas(filename):
    return send_from_directory(DOWNLOADS_FOLDER, filename)

@app.route('/api/procesar_descargas', methods=['POST'])
def api_procesar_descargas():
    """
    Recibe una lista de NOMBRES de archivos que ya están en Descargas,
    los busca y genera el PDF usando tu función existente.
    """
    data = request.json
    lista_nombres = data.get('archivos', [])
    layout = data.get('layout', 'full')
    position = data.get('position', 'center')
    
    if not lista_nombres:
        return jsonify({"error": "No seleccionaste nada"}), 400

    # Construir las rutas completas
    rutas_completas = []
    for nombre in lista_nombres:
        ruta = os.path.join(DOWNLOADS_FOLDER, nombre)
        if os.path.exists(ruta):
            rutas_completas.append(ruta)
    
    if not rutas_completas:
        return jsonify({"error": "No se encontraron los archivos"}), 404

    try:
        # REUTILIZAMOS TU FUNCIÓN 'crear_pdf_imagenes' (la que hicimos antes)
        # Asegúrate de que esa función esté accesible aquí
        ruta_pdf = crear_pdf_imagenes(rutas_completas, layout, position)
        
        # Devolvemos la URL para que el frontend descargue el PDF
        # Ojo: necesitamos una ruta para descargar el PDF generado en 'uploads'
        nombre_pdf = os.path.basename(ruta_pdf)
        return jsonify({"success": True, "pdf_url": f"/bajar_pdf/{nombre_pdf}"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Ruta auxiliar para entregar el PDF generado
@app.route('/bajar_pdf/<filename>')
def bajar_pdf(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

# Agrega esto a tu app.py

@app.route('/api/listar_descargas_json')
def api_listar_descargas_json():
    """Devuelve la lista de archivos en formato JSON para el auto-refresh"""
    imagenes = obtener_imagenes_recientes()
    return jsonify(imagenes)


import io # <--- AGREGA ESTO AL INICIO CON TUS IMPORTS

# ... (Tu código anterior) ...

@app.route('/thumbnail/<path:filename>')
def serve_thumbnail(filename):
    """Genera una miniatura ligera al vuelo para que la galería no se trabe"""
    ruta_completa = os.path.join(DOWNLOADS_FOLDER, filename)
    
    if not os.path.exists(ruta_completa):
        return "", 404

    try:
        # Abrimos la imagen original
        with Image.open(ruta_completa) as img:
            # Convertimos a RGB si es necesario (para evitar errores con PNGs transparentes al guardar como JPEG)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                
            # La reducimos a un tamaño máximo de 200x200 píxeles
            img.thumbnail((200, 200))
            
            # La guardamos en memoria (RAM) no en disco, para ser rápidos
            byte_io = io.BytesIO()
            img.save(byte_io, 'JPEG', quality=70) # Calidad baja para vista previa rápida
            byte_io.seek(0)
            
            return send_file(byte_io, mimetype='image/jpeg')
            
    except Exception as e:
        print(f"Error thumbnail: {e}")
        # Si falla (ej. archivo corrupto), mandamos un placeholder o nada
        return "", 500

import pythoncom
import win32com.client

# --- FUNCIONES DE CONVERSIÓN (MOTORES) ---

def convertir_word_a_pdf(input_path, output_path):
    pythoncom.CoInitialize()
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    doc = None
    try:
        doc = word.Documents.Open(input_path)
        # 17 = wdFormatPDF
        doc.SaveAs(output_path, FileFormat=17)
    finally:
        if doc: doc.Close()
        word.Quit()

def convertir_excel_a_pdf(input_path, output_path):
    pythoncom.CoInitialize()
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False # Evita popups de "Guardar cambios?"
    wb = None
    try:
        wb = excel.Workbooks.Open(input_path)
        # 0 = xlTypePDF
        # Ajustamos todas las hojas para que se impriman
        wb.ExportAsFixedFormat(0, output_path)
    finally:
        if wb: wb.Close(False)
        excel.Quit()

def convertir_ppt_a_pdf(input_path, output_path):
    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")
    # PPT a veces necesita arrancar visible minimizado para funcionar bien
    # ppt.Visible = True 
    pres = None
    try:
        pres = ppt.Presentations.Open(input_path, WithWindow=False)
        # 32 = ppSaveAsPDF
        pres.SaveAs(output_path, 32)
    finally:
        if pres: pres.Close()
        ppt.Quit()

# --- RUTA API PARA DOCUMENTOS ---

@app.route('/api/convertir_documento', methods=['POST'])
def api_convertir_documento():
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo"}), 400
    
    archivo = request.files['file']
    if archivo.filename == '':
        return jsonify({"error": "Nombre vacío"}), 400

    # 1. Guardar archivo original (Word/Excel/PPT)
    filename = secure_filename(archivo.filename)
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    archivo.save(input_path)
    
    # 2. Definir ruta de salida (PDF)
    nombre_base = os.path.splitext(filename)[0]
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{nombre_base}.pdf")
    
    # 3. Detectar tipo y llamar al motor correcto
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext in ['.doc', '.docx']:
            convertir_word_a_pdf(os.path.abspath(input_path), os.path.abspath(output_path))
            
        elif ext in ['.xls', '.xlsx']:
            convertir_excel_a_pdf(os.path.abspath(input_path), os.path.abspath(output_path))
            
        elif ext in ['.ppt', '.pptx']:
            convertir_ppt_a_pdf(os.path.abspath(input_path), os.path.abspath(output_path))
            
        else:
            return jsonify({"error": "Formato no soportado. Solo Office."}), 400
            
        # Devolver URL para descargar
        return jsonify({
            "success": True, 
            "pdf_url": f"/bajar_pdf/{nombre_base}.pdf"
        })

    except Exception as e:
        print(f"Error conversión Office: {e}")
        return jsonify({"error": f"Fallo al convertir: {str(e)}"}), 500

# Ruta para servir la página (Frontend)
@app.route('/doc-to-pdf')
def pagina_documentos():
    return render_template('doc-to-pdf.html')

@app.route('/api/remove_uploads', methods=['POST'])
def api_remove_uploads():
    folder = app.config['UPLOAD_FOLDER']
    archivos_borrados = 0
    errores = 0

    # Listar todo lo que hay en uploads
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            # Verificar que sea un archivo (no borrar subcarpetas si las hubiera)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path) # unlink es lo mismo que remove
                archivos_borrados += 1
        except Exception as e:
            # Si el archivo está abierto por Word/Sumatra, fallará. Lo ignoramos.
            print(f"No se pudo borrar {filename}: {e}")
            errores += 1

    return jsonify({
        "success": True, 
        "msg": f"Se eliminaron {archivos_borrados} archivos. ({errores} estaban en uso y se quedaron)."
    })

# ... (imports anteriores) ...

# 1. FUNCIÓN REUTILIZABLE DE IMPRESIÓN (Refactorización)
# Sacamos la lógica difícil a una función sola para usarla en todos lados
def ejecutar_impresion(ruta_archivo, impresora, copias, rango, formato, color):
    # Construir settings de Sumatra
    settings = []
    settings.append(f"{copias}x")
    if rango and rango.strip(): settings.append(rango)
    settings.append(f"paper={formato}")
    settings.append(f"color={color}")
    
    settings_str = ",".join(settings)

    comando = [
        SUMATRA_PATH,
        "-print-to", impresora,
        "-print-settings", settings_str,
        "-silent",
        ruta_archivo
    ]
    
    subprocess.run(comando, check=True)

# 2. BUSCADOR DE PDFs
def obtener_pdfs_descargas():
    pdfs = []
    try:
        for entry in os.scandir(DOWNLOADS_FOLDER):
            if entry.is_file() and entry.name.lower().endswith('.pdf'):
                pdfs.append({
                    "nombre": entry.name,
                    "fecha": entry.stat().st_mtime,
                    "fecha_legible": time.ctime(entry.stat().st_mtime),
                    "size": f"{entry.stat().st_size / 1024:.1f} KB" # Tamaño en KB
                })
        # Ordenar: más recientes primero
        pdfs.sort(key=lambda x: x['fecha'], reverse=True)
    except Exception as e:
        print(f"Error leyendo PDFs: {e}")
    return pdfs

# --- RUTAS NUEVAS ---

@app.route('/pdfs')
def pagina_pdfs():
    return render_template('pdfs.html')

@app.route('/api/listar_pdfs_json')
def api_listar_pdfs():
    """Para el auto-refresh de la lista"""
    return jsonify(obtener_pdfs_descargas())

@app.route('/api/imprimir_local', methods=['POST'])
def api_imprimir_local():
    """
    Imprime un archivo que YA existe en Descargas (sin subirlo de nuevo).
    """
    data = request.json
    nombre_archivo = data.get('archivo')
    impresora = data.get('impresora')
    
    # Validar que exista
    ruta_completa = os.path.join(DOWNLOADS_FOLDER, nombre_archivo)
    if not os.path.exists(ruta_completa):
        return jsonify({"success": False, "msg": "El archivo ya no existe"}), 404

    try:
        ejecutar_impresion(
            ruta_completa,
            impresora,
            data.get('copias', '1'),
            data.get('rango', ''),
            data.get('formato', 'Letter'),
            data.get('color', 'color')
        )
        return jsonify({"success": True, "msg": "Enviado a impresora"})
    except Exception as e:
        return jsonify({"success": False, "msg": f"Error: {str(e)}"}), 500

# IMPORTANTE: Modifica tu ruta anterior 'api_subir_y_imprimir' para usar la nueva función
# (Solo te pongo el cambio clave para que no repitas código)
# ... dentro de api_subir_y_imprimir ...
# en lugar de todo el bloque 'settings...', solo llama:
# ejecutar_impresion(ruta_pdf, impresora, copias, rango, formato, modo_color)

@app.route('/api/borrar_archivos_descargas', methods=['POST'])
def api_borrar_archivos_descargas():
    data = request.json
    lista_nombres = data.get('archivos', [])
    
    if not lista_nombres:
        return jsonify({"success": False, "msg": "No seleccionaste nada"}), 400

    borrados = 0
    errores = []

    for nombre in lista_nombres:
        # SEGURIDAD: basename quita cualquier ruta relativa (ej. ../windows)
        # Solo permite el nombre del archivo final.
        nombre_limpio = os.path.basename(nombre)
        ruta_completa = os.path.join(DOWNLOADS_FOLDER, nombre_limpio)
        
        try:
            if os.path.exists(ruta_completa):
                os.remove(ruta_completa) # Borrado permanente
                borrados += 1
        except Exception as e:
            print(f"Error borrando {nombre}: {e}")
            errores.append(str(e))

    return jsonify({
        "success": True, 
        "msg": f"Se eliminaron {borrados} archivos.",
        "errores": errores
    })
# Definimos las categorías de archivos que aceptamos
TIPOS_ACEPTADOS = {
    'imagen': {
        'ext': {'.jpg', '.jpeg', '.png', '.bmp', '.webp'},
        'icon': '📸',
        'desc': 'Imagen',
        'convertible': True,
        'endpoint': '/api/convertir' # Endpoint que ya creamos antes
    },
    'office': {
        'ext': {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'},
        'icon': '📝',
        'desc': 'Documento Office',
        'convertible': True,
        'endpoint': '/api/convertir_documento' # Endpoint que ya creamos antes
    },
    'pdf': {
        'ext': {'.pdf'},
        'icon': '📑',
        'desc': 'Archivo PDF',
        'convertible': False, # Ya es PDF
        'msg': 'Este archivo ya está listo para imprimir.'
    }
}

@app.route('/api/identificar', methods=['POST'])
def api_identificar():
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo"}), 400
    
    file = request.files['file']
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    # 1. Buscar en nuestras categorías
    resultado = {
        "tipo": "desconocido",
        "icon": "❓",
        "desc": "Archivo Desconocido",
        "convertible": False,
        "msg": "No se reconoce el formato o no es compatible."
    }
    
    for key, info in TIPOS_ACEPTADOS.items():
        if ext in info['ext']:
            resultado = {
                "tipo": key,
                "icon": info['icon'],
                "desc": info['desc'],
                "convertible": info['convertible'],
                "endpoint": info.get('endpoint', ''),
                "msg": info.get('msg', 'Listo para convertir.')
            }
            break
            
    return jsonify(resultado)

@app.route('/analitic-type-img')
def pagina_analizador():
    return render_template('analitic-type-img.html')
if __name__ == '__main__':
    app.run(debug=True, port=5000)