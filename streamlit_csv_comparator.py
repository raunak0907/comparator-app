import streamlit as st
import pandas as pd
import io
import csv
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

KEYS = ['UNIT_PERNO', 'SAIL_PERNO']
EXCLUDE_COLUMNS = ['YYYYMM']

st.set_page_config(page_title="CSV Comparator", layout="wide")
st.title("📊 CSV Comparator")

def read_csv_file(uploaded_file):
    decoded = uploaded_file.read().decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    rows = list(reader)
    key_col = next((k for k in KEYS if k in rows[0]), None)
    if not key_col:
        st.error(f"No valid key column found in {uploaded_file.name}")
        return {}, None
    return {row[key_col].strip(): row for row in rows if row[key_col].strip()}, key_col

def compare_files(master_data, slave_data):
    all_columns = set()
    for data in [master_data, slave_data]:
        for row in data.values():
            all_columns.update(col for col in row if col not in EXCLUDE_COLUMNS)

    grouped_diff = []
    grouped_new = []

    for emp_key in set(master_data) | set(slave_data):
        m_row = master_data.get(emp_key, {})
        s_row = slave_data.get(emp_key, {})

        if not m_row:
            sub_rows = [
                {'Field': col, 'Old': "--- NOT IN MASTER ---", 'New': str(s_row[col])}
                for col in s_row if col not in EXCLUDE_COLUMNS and s_row.get(col)
            ]
            if sub_rows:
                grouped_new.append({'Employee': emp_key, 'Changes': sub_rows})
        elif not s_row:
            continue
        else:
            diffs = [
                {'Field': col, 'Old': str(m_row.get(col, "")).strip(), 'New': str(s_row.get(col, "")).strip()}
                for col in all_columns
                if str(m_row.get(col, "")).strip() != str(s_row.get(col, "")).strip()
            ]
            if diffs:
                grouped_diff.append({'Employee': emp_key, 'Changes': diffs})

    return grouped_diff, grouped_new

def generate_pdf(groups, category):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    wrap = ParagraphStyle(name='Wrapped', parent=styles['BodyText'], alignment=0)

    title = "Differences Report" if category == 'diff' else "New Joinees Report"
    elements.append(Paragraph(title, styles['Title']))

    for group in groups:
        elements.append(Paragraph(f"Employee: {group['Employee']}", styles['Heading4']))
        data = [['Field', 'Old Value', 'New Value']]
        for change in group['Changes']:
            data.append([
                Paragraph(change['Field'], wrap),
                Paragraph(change['Old'], wrap),
                Paragraph(change['New'], wrap)
            ])
        table = Table(data, colWidths=[120, 170, 170], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def flatten_for_excel(grouped):
    flat = []
    for group in grouped:
        for change in group['Changes']:
            flat.append({
                'Employee': group['Employee'],
                'Field': change['Field'],
                'Old Value': change['Old'],
                'New Value': change['New']
            })
    return pd.DataFrame(flat)

# --- Upload UI ---
master_file = st.file_uploader("Upload Master CSV", type="csv", key="master")
slave_file = st.file_uploader("Upload Slave CSV", type="csv", key="slave")

if master_file and slave_file:
    master_data, _ = read_csv_file(master_file)
    slave_data, _ = read_csv_file(slave_file)

    if master_data and slave_data:
        grouped_diff, grouped_new = compare_files(master_data, slave_data)

        st.success(f"Comparison complete: {len(grouped_diff)} changed, {len(grouped_new)} new joinees")

        tabs = st.tabs(["🔍 Grouped Differences", "🆕 Grouped New Joinees"])

        with tabs[0]:
            for group in grouped_diff:
                with st.expander(f"Employee: {group['Employee']}"):
                    df = pd.DataFrame(group['Changes'])
                    st.table(df)

            if grouped_diff:
                st.download_button("⬇️ Download Excel", flatten_for_excel(grouped_diff).to_excel(index=False, engine='openpyxl'), file_name="differences_report.xlsx")
                st.download_button("⬇️ Download PDF", generate_pdf(grouped_diff, 'diff'), file_name="differences_report.pdf")

        with tabs[1]:
            for group in grouped_new:
                with st.expander(f"Employee: {group['Employee']}"):
                    df = pd.DataFrame(group['Changes'])
                    st.table(df)

            if grouped_new:
                st.download_button("⬇️ Download Excel", flatten_for_excel(grouped_new).to_excel(index=False, engine='openpyxl'), file_name="new_joinees_report.xlsx")
                st.download_button("⬇️ Download PDF", generate_pdf(grouped_new, 'new'), file_name="new_joinees_report.pdf")
