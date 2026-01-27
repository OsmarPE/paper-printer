import os
import subprocess
from flask import Flask, request, send_file, jsonify, render_template
from werkzeug.utils import secure_filename
from fpdf import FPDF
from PIL import Image
import win32print
import win32api

app = Flask(__name__)

# CONFIGURACIÓN
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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
            estado_txt = "Lista 🟢" if estado_code == 0 else f"Atención/Ocupada ({estado_code}) 🟠"
            
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

@app.route('/impresoras')
def pagina_impresoras():
    # Muestra el panel de gestión
    lista = obtener_impresoras()
    return render_template('impresoras.html', impresoras=lista)

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)