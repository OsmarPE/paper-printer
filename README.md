# 🖨️ Sistema de Gestión para Papelería (PapeleríaPro)

Este proyecto es una aplicación web local diseñada para automatizar tareas comunes en una papelería, como la conversión de imágenes y documentos a PDF, la gestión de impresoras y la visualización rápida de archivos descargados.

## 📋 Requisitos Previos

Antes de instalar, asegúrate de que la computadora tenga:

1.  **Python 3.10 o superior**: [Descargar aquí](https://www.python.org/downloads/).
    * *IMPORTANTE:* Al instalar, marca la casilla **"Add Python to PATH"**.
2.  **LibreOffice**: [Descargar aquí](https://es.libreoffice.org/).
    * Necesario para convertir Word/Excel/PowerPoint a PDF.
3.  **SumatraPDF (Portable)**:
    * Descarga el ejecutable portable `.zip` o `.exe` de [aquí](https://www.sumatrapdfreader.org/download-free-pdf-viewer).
    * Renombra el archivo a `SumatraPDF.exe`.
    * Colócalo en la carpeta raíz de este proyecto.

## 🚀 Instalación y Ejecución Automática (Recomendado)

Solo necesitas hacer doble clic en el archivo:
`iniciar_sistema.bat`

Este script se encargará de:
1.  Crear el entorno virtual (`venv`) si no existe.
2.  Instalar las librerías necesarias.
3.  Abrir el navegador automáticamente.
4.  Iniciar el servidor.

---

## ⚙️ Instalación Manual (Paso a paso)

Si prefieres hacerlo por consola, sigue estos pasos:

### 1. Crear Entorno Virtual
Abre una terminal en la carpeta del proyecto y ejecuta:
```bash
python -m venv venv
```


### 2. Activar Entorno Virtual
```bash
source venv/Scripts/activate
```

### 3. Instalar los paquetes
```bash
pip install -r requirements.txt
```


### 4. Ejecutar el programa
```bash
python app.py
```

### 5. Ejecutar el proyecto
Entra a tu navegador  e ingresa a la siguiente url: 
```bash
http://localhost:5000
```





