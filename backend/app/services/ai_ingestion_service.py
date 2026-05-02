import csv
import io
import json
from typing import Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.document_extractor import ExtractedDocument
from app.services.llm_client import extract_content, smart_complete

log = get_logger("app.services.ai_ingestion")

from pydantic import Field

class ExtractedFinancialItem(BaseModel):
    standard_metric: str
    original_name: str
    values: List[float] = Field(
        ..., 
        description="A list of numeric amounts exactly matching the order of the 'periods' array. Use 0.0 if missing."
    )

class LLMFinancialExtraction(BaseModel):
    currency: Optional[str] = None
    scale: Optional[str] = None
    periods: List[str]
    financial_data: List[ExtractedFinancialItem]
    unmapped_items: List[str]

SYSTEM_PROMPT = """Actúa como un Analista Financiero Experto y un Ingeniero de Datos especializado en la extracción y normalización de estados financieros. 

Tu objetivo es recibir datos en texto plano o formato CSV (provenientes de Excel) de diferentes empresas y mapearlos a un esquema de datos JSON estándar y predecible, sin importar el formato original, el idioma o la estructura del documento.

Sigue estrictamente estas reglas:

1. RECONOCIMIENTO DE ESTRUCTURA Y PERIODOS:
- Analiza el documento para entender su orientación. Las fechas/periodos (ej. '31/12/21', '2024', 'LTM', '3T25') pueden estar en la primera fila (como cabeceras) o en la primera columna. Identifícalas y úsalas como el eje temporal.
- Ignora filas vacías, subtítulos irrelevantes o texto introductorio (ej. "P&G (Mn€)", "Income Statement | TIKR.com").

2. MAPEO SEMÁNTICO (Fuzzy Matching):
- Los conceptos financieros vendrán en diferentes idiomas (Inglés, Español) y usarán sinónimos. Debes mapearlos a nuestras "Métricas Estándar" en inglés. 
- Ejemplos de mapeo:
  * "Revenue", "Importe neto de la cifra de negocios", "Ventas" -> mapear a "Revenue"
  * "Cost of Goods Sold", "Aprovisionamientos", "COGS" -> mapear a "Cost of Goods Sold"
  * "Beneficio Neto", "Net Income", "Resultado del ejercicio" -> mapear a "Net Income"
  * "Efectivo y equivalentes", "Cash and equivalents" -> mapear a "Cash & Equivalents"
  * "Gastos de personal", "Sueldos", "Other OpEx" -> mapear a "Other OpEx"
  * "Deuda a corto plazo", "Short term debt" -> mapear a "Short-Term Debt"
- IMPORTANTE: Debes utilizar EXACTAMENTE una de las siguientes métricas estándar permitidas. No inventes nombres.
  * PNL: "Revenue", "Cost of Goods Sold", "Gross Profit", "SG&A", "R&D", "D&A", "Amortization of Intangibles", "Other OpEx", "EBIT", "Interest Income", "Interest Expense", "Other Non-Operating Income / (Expense)", "EBT", "Tax", "Net Income"
  * BS: "PP&E Gross", "Accumulated Depreciation", "Net PP&E", "Intangibles Gross", "Accumulated Amortization", "Net Intangibles", "Goodwill", "Inventories", "Accounts Receivable", "Prepaid Expenses & Other Current Assets", "Accounts Payable", "Accrued Liabilities", "Other Current Liabilities", "Other Long-Term Liabilities", "Cash & Equivalents", "Non-Operating Assets", "Short-Term Debt", "Long-Term Debt", "Share Capital", "Retained Earnings", "Other Equity (AOCI, Treasury Stock, etc.)"
  * CF: "Net Income", "D&A Add-back", "Amortization of Intangibles Add-back", "Changes in Working Capital", "Operating Cash Flow", "Capex", "Acquisitions / Disposals", "Investing Cash Flow", "Debt Issuance / Repayment", "Dividends Paid", "Share Issuance / Buyback", "Financing Cash Flow", "Net Change in Cash"
- Si no encuentras un mapeo adecuado entre estas opciones, ponlo en "unmapped_items".

3. NORMALIZACIÓN DE DATOS NUMÉRICOS:
- Convierte todos los valores a números flotantes (float).
- Elimina cualquier texto de las celdas de valor (ej. símbolos de moneda como €, $, texto explicativo).
- Interpreta correctamente los valores negativos (ya sea que vengan con el signo '-' o entre paréntesis '( )').
- Detecta si los números están en unidades absolutas, miles o millones (basado en el contexto o encabezados como 'Mn€') e indícalo en el JSON final.
- Los porcentajes (ej. % Change YoY) conviértelos a formato decimal (ej. 15% o 0.15 debe ser 0.15).

4. MANEJO DE ERRORES:
- Si encuentras una métrica que no reconoces o no puedes mapear de forma segura a nuestro esquema estándar, agrégala a un array de "unmapped_items" en lugar de forzar un mapeo incorrecto y causar un error.

5. FORMATO DE SALIDA ESTRICTO:
- Debes devolver ÚNICAMENTE el objeto estructurado válido según el esquema. No incluyas explicaciones, saludos ni formato Markdown adicional.
- En el campo 'values' de cada ExtractedFinancialItem, las claves (keys) del diccionario DEBEN ser exactamente los periodos detectados (ej. "2021", "2022") y los valores (values) DEBEN ser los importes numéricos correspondientes para ese periodo. ¡No dejes el diccionario 'values' vacío!
"""

def document_to_csv(doc: ExtractedDocument) -> str:
    """Convierte el documento extraído a un string CSV para el LLM."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    for sheet in doc.sheets:
        writer.writerow([f"--- SHEET: {sheet.name} ---"])
        for row in sheet.rows:
            writer.writerow([str(x) if x is not None else "" for x in row])
        writer.writerow([])
        
    return output.getvalue()

def run_ai_extraction(
    user_id: str, 
    extracted_doc: ExtractedDocument, 
    db: Session
) -> LLMFinancialExtraction:
    """Ejecuta el LLM para procesar el documento completo de una sola vez."""
    csv_text = document_to_csv(extracted_doc)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Aquí están los datos financieros:\n\n{csv_text}"}
    ]
    
    # In litellm, if response_format is a Pydantic BaseModel class,
    # it uses the Structured Outputs feature of OpenAI / Gemini automatically.
    res = smart_complete(
        user_id=user_id,
        db=db,
        messages=messages,
        response_format=LLMFinancialExtraction,
    )
    
    content_str = extract_content(res)
    
    # Robust JSON parsing (handles potential Markdown markers)
    def clean_json_string(s: str) -> str:
        s = s.strip()
        if s.startswith("```json"):
            s = s[7:]
        if s.startswith("```"):
            s = s[3:]
        if s.endswith("```"):
            s = s[:-3]
        return s.strip()

    cleaned_content = clean_json_string(content_str)
    
    try:
        data_dict = json.loads(cleaned_content)
        return LLMFinancialExtraction(**data_dict)
    except Exception as e:
        log.error(f"Failed to parse AI output: {e}\nContent: {content_str[:500]}...")
        raise ValueError(f"Failed to decode LLM JSON output: {str(e)}")
