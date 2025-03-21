import streamlit as st
import requests
from decouple import config
import re
import pandas as pd
import unicodedata


BASE_URL = config("URL")  
API_TOKEN = config("TOKEN") 
LINK_URL= config("LINK_URL")
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def clean_string(input_string: str) -> str:
    cleaned = input_string.strip().lower()
    cleaned = unicodedata.normalize('NFD', cleaned)
    cleaned = re.sub(r'[^\w\s.,!?-]', '', cleaned)
    cleaned = re.sub(r'[\u0300-\u036f]', '', cleaned)
    return cleaned

def canvas_request(session, method, endpoint, payload=None, paginated=False):
    if not BASE_URL:
        raise ValueError("BASE_URL no está configurada. Usa set_base_url() para establecerla.")
    
    url = f"{BASE_URL}{endpoint}"
    results = []
    
    try:
        while url:
            response = session.request(method.upper(), url, json=payload, headers=HEADERS)
            if not response.ok:
                st.error(f"Error en la petición a {url} ({response.status_code}): {response.text}")
                return None
            data = response.json()
            if paginated:
                results.extend(data)
                url = response.links.get("next", {}).get("url")
            else:
                return data
        return results if paginated else None
    except requests.exceptions.RequestException as e:
        st.error(f"Excepción en la petición a {url}: {e}")
        return None

st.set_page_config(page_title="Analizador de puntajes de Rubricas 📝", layout="wide")
st.title("Analizador de puntajes de Rubricas 📝")

# Área de texto para ingresar uno o más IDs
ids_input = st.text_area("Ingresa uno o más IDs (separados por coma, espacio o salto de línea):")

def format_points(value, expected):
    """Formatea los puntos con color según el valor esperado."""
    if value == expected:
        return f":green[{value}]"
    return f":red[{value}]"

if st.button("Analizar"):
    ids_list = re.split(r'[,\s]+', ids_input.strip())
    ids_list = [id.strip() for id in ids_list if id.strip()]
    
    if not ids_list:
        st.error("Por favor ingresa al menos un ID.")
    else:
        session = requests.Session()
        
        for course_id in ids_list:
            if not course_id.isdigit():
                st.warning(f"El ID '{course_id}' no es un id válido.")
                continue
                
            resultados = []
            course_info = canvas_request(session, "GET", f"/courses/{course_id}")
            account_info = canvas_request(session, "GET", f"/accounts/{course_info.get('account_id')}")
            st.write(f"#### {course_info.get('name')} ([{course_info.get('id')}]({LINK_URL}/courses/{course_id})) - {course_info.get('sis_course_id')}"  ) 
            st.write(f"###### {account_info.get('name')} ([{account_info.get('id')}]({LINK_URL}/accounts/{course_info.get('account_id')}))")
            assignments = canvas_request(session, "GET", f"/courses/{course_id}/assignments")
            
            if not assignments:
                resultados.append({
                    "Link": "No disponible",
                    "Assignment Name": "No hay tareas",
                    "Rúbrica": "Error al obtener datos",
                    "Puntos Totales": "Error al obtener datos",
                    "Puntos Destacado": "Error al obtener datos",
                    "Puntos Habilitado": "Error al obtener datos",
                    "Puntos En desarrollo": "Error al obtener datos",
                    "Puntos No logrado": "Error al obtener datos",
                })
                continue
            
            for assignment in assignments: 
                assignment_id = assignment.get("id")
                assignment_data = canvas_request(session, "GET", f"/courses/{course_id}/assignments/{assignment_id}")
                
                if not assignment_data:
                    resultados.append({
                        "Link": "No disponible",
                        "Assignment Name": "Error al obtener datos",
                        "Rúbrica": "Error al obtener datos",
                        "Puntos Totales": "Error al obtener datos",
                        "Puntos Destacado": "Error al obtener datos",
                        "Puntos Habilitado": "Error al obtener datos",
                        "Puntos En desarrollo": "Error al obtener datos",
                        "Puntos No logrado": "Error al obtener datos",
                    })
                    continue
                
                rubric = assignment_data.get("rubric")
                rubric_settings = assignment_data.get("rubric_settings")
                
                if not rubric:
                    resultados.append({
                        "Link": "No disponible",
                        "Assignment Name": assignment_data.get("name", "Sin nombre"),
                        "Rúbrica": "Sin rúbrica",
                        "Puntos Totales": "Error al obtener datos",
                        "Puntos Destacado": "Error al obtener datos",
                        "Puntos Habilitado": "Error al obtener datos",
                        "Puntos En desarrollo": "Error al obtener datos",
                        "Puntos No logrado": "Error al obtener datos",
                    })
                    continue
                
                rubric_title = rubric_settings.get("title", "Sin título")
                points_possible = int(rubric_settings.get("points_possible", 0))
                
                destacado = 0
                habilitado = 0
                en_desarrollo = 0
                no_logrado = 0
                
                for criterio in rubric:
                    for rating in criterio.get("ratings", []):
                        descripcion = clean_string(rating.get("description", ""))
                        puntos = int(rating.get("points", 0))
                        #st.write(descripcion)
                        if descripcion == clean_string("Destacado") or descripcion.startswith(clean_string("Destacado")):
                            destacado += puntos
                        elif descripcion == clean_string("Habilitado") or descripcion.startswith(clean_string("Habilitado")):
                            habilitado += puntos
                        elif descripcion == clean_string("En desarrollo") or descripcion.startswith(clean_string("En desarrollo")):
                            en_desarrollo += puntos
                        elif descripcion == clean_string("No logrado") or descripcion.startswith(clean_string("No logrado")):
                            no_logrado += puntos
                
                resultados.append({
                    "Link": f"[Ver Tarea]({LINK_URL}/courses/{course_id}/assignments/{assignment_id})",
                    "Assignment Name": assignment_data.get("name", "Sin nombre"),
                    "Rúbrica": rubric_title,
                    "Puntos Totales": points_possible,
                    "Puntos Destacado": format_points(destacado, 100),
                    "Puntos Habilitado": format_points(habilitado, 60),
                    "Puntos En desarrollo": format_points(en_desarrollo, 30),
                    "Puntos No logrado": format_points(no_logrado, 0),
                })
        
            df = pd.DataFrame(resultados)

            # Usar st.write() con unsafe_allow_html para renderizar markdown en la tabla
            st.markdown(df.to_markdown(index=False), unsafe_allow_html=True)