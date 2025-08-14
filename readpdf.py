# -*- coding: utf-8 -*-
import os
import csv
import re
import datetime
import configparser
import PyPDF2
import logging
from typing import List, Dict, Optional

def setup_logging(log_file: str) -> None:
    """Configura el sistema de logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def read_config() -> Dict:
    #Lee la configuración desde el archivo setup.ini"""
    config = configparser.ConfigParser()
    if not os.path.exists('setup.ini'):
        config['DEFAULT'] = {
            'source_folder': r'C:\pdf\br',
            'output_folder': r'C:\pdf\br\output',
            'fields_to_extract': 'Nome,PIS/PASEP/NIT,Valor Base para Fins'
        }
        with open('setup.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    
    config.read('setup.ini', encoding='utf-8')
    return {
        'source_folder': config['DEFAULT']['source_folder'],
        'output_folder': config['DEFAULT']['output_folder'],
        'fields_to_extract': [f.strip() for f in config['DEFAULT']['fields_to_extract'].split(',')]
    }

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae texto de un archivo PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + '\n'
            return text
    except Exception as e:
        logging.error(f"Error al leer el archivo {pdf_path}: {str(e)}")
        return ''

def clean_value(value: str) -> str:
    #Limpia el valor eliminando R$  lo que está después de Base:"""
    if not value:
        return value
    
    # Eliminar "R$" si existe
    value = value.replace('R$', '').strip()
    
    # Eliminar todo lo que está después de "Base:"
    if 'Base:' in value:
        value = value.split('Base:')[0].strip()
    
    return value

def find_field_value(text: str, field_name: str) -> Optional[str]:
    #Busca el valor de un campo en el texto usando expresiones regulares
    #con patrones específicos para cada tipo de campo
    
    patterns = {
        "Valor Base para Fins Rescisorios": r"Valor Base para Fins :\s*(R\$\s*[\d\.,]+\s*.*?)(?:\s*Base:|$)",
        "Nome": r"Nome[:\s]*([^\n]+)",
        "PIS/PASEP/NIT": r"(PIS/PASEP/NIT|PIS)[:\s]*([\d\.\-/]+)"
    }
    
    # Selecciona el patrón según el campo buscado
    pattern = patterns.get(field_name, f"{field_name}[:\s]*([^\n]+)")
    
    # Búsqueda con expresión regular
    match = re.search(pattern, text, re.IGNORECASE)
    
    if not match:
        return None
    
    # Para PIS/PASEP/NIT que tiene dos grupos en el patrón
    if field_name == "PIS/PASEP/NIT" and len(match.groups()) > 1:
        return match.group(2).strip()
    
    return clean_value(match.group(1).strip())

def process_pdfs(config: Dict) -> List[Dict]:
    """Procesa todos los PDFs en la carpeta fuente"""
    results = []
    source_folder = config['source_folder']
    fields = config['fields_to_extract']
    
    if not os.path.exists(source_folder):
        logging.error(f"La carpeta fuente no existe: {source_folder}")
        return results
    
    pdf_files = [f for f in os.listdir(source_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        logging.warning("No se encontraron archivos PDF en la carpeta fuente")
        return results
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(source_folder, pdf_file)
        logging.info(f"Procesando archivo: {pdf_file}")
        
        text = extract_text_from_pdf(pdf_path)
        if not text:
            continue
        
        record = {'Archivo': pdf_file}
        for field in fields:
            value = find_field_value(text, field)
            record[field] = value if value else 'No encontrado'
            logging.debug(f"Campo {field}: {record[field]}")
        
        results.append(record)
    
    return results

def save_results_to_csv(results: List[Dict], output_folder: str) -> str:
    """Guarda los resultados en un archivo CSV con nombre basado en la fecha/hora actual"""
    if not results:
        return ''
    
    os.makedirs(output_folder, exist_ok=True)
    
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    csv_filename = f"br_{timestamp}.csv"
    csv_path = os.path.join(output_folder, csv_filename)
    
    fieldnames = set()
    for record in results:
        fieldnames.update(record.keys())
    fieldnames = sorted(fieldnames)
    
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Limpiar los valores antes de escribir
            for record in results:
                cleaned_record = {k: clean_value(v) if isinstance(v, str) else v for k, v in record.items()}
                writer.writerow(cleaned_record)
                
        logging.info(f"Archivo CSV generado exitosamente: {csv_path}")
        return csv_path
    except Exception as e:
        logging.error(f"Error al generar archivo CSV: {str(e)}")
        return ''

def main():
    # Configurar sistema para manejar UTF-8 en la consola de Windows
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # Leer configuración
    config = read_config()
    
    # Configurar logging
    os.makedirs(config['output_folder'], exist_ok=True)
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(config['output_folder'], f"br_{timestamp}.log")
    setup_logging(log_file)
    
    logging.info("Iniciando procesamiento de archivos PDF")
    logging.info(f"Carpeta fuente: {config['source_folder']}")
    logging.info(f"Carpeta de salida: {config['output_folder']}")
    logging.info(f"Campos a extraer: {', '.join(config['fields_to_extract'])}")
    
    # Procesar archivos PDF
    results = process_pdfs(config)
    
    if results:
        csv_path = save_results_to_csv(results, config['output_folder'])
        if csv_path:
            logging.info(f"Proceso completado. {len(results)} registros procesados.")
        else:
            logging.error("No se pudo generar el archivo CSV")
    else:
        logging.warning("No se procesaron registros. Verifique los archivos PDF de entrada.")

if __name__ == "__main__":
    main()