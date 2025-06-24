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
st.title("📋 Compare Two CSVs Easily")

st.markdown("Upload your **Master** and **Slave** CSV files to see what's changed or who's new.")

# --- File Upload ---
master_file = st.file_uploader("📤 Upload Master CSV", type="csv", key="master")
slave_file = st.file_uploader("📤 Upload Latest CSV (to compare)", type="csv", key="slave")

def read_csv_file(uploaded_file):
    decoded = uploaded_file.read().decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    rows = list(reader)
    key_col = next((k for k in KEYS if k in rows[0]), None)
    if not key_col:
        st.error(f"❌ No valid key column found in {uploaded_file.name}")
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
                {'Field': col, 'Old': "--- Not in Master ---", 'New': str(s_row[col])}
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

    title = "What's Changed" if category == 'diff' else "New Joinees"
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

# --- Process CSVs ---
if master_file and slave_file:
    master_data, _ = read_csv_file(master_file)
    slave_data, _ = read_csv_file(slave_file)

    if master_data and slave_data:
        grouped_diff, grouped_new = compare_files(master_data, slave_data)

        st.success(f"✅ Done! Found {len(grouped_diff)} changed records and {len(grouped_new)} new joiners.")

        tabs = st.tabs(["🔍 See What Changed", "🆕 Who's New?"])

        
        with tabs[0]:
            st.subheader("⬇️ Download Reports")
            pdf_diff = generate_pdf(grouped_diff or [{'Employee': 'N/A', 'Changes': []}], 'diff')
            st.download_button("📄 Download PDF (Changes)", data=pdf_diff, file_name="differences_report.pdf", mime="application/pdf", help="Download all changes as PDF")

            excel_diff_df = flatten_for_excel(grouped_diff or [])
            excel_diff_buffer = io.BytesIO()
            excel_diff_df.to_excel(excel_diff_buffer, index=False, engine='openpyxl')
            excel_diff_buffer.seek(0)
            st.download_button("📊 Download Excel (Changes)", data=excel_diff_buffer, file_name="differences_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", help="Download all changes as Excel")

            st.divider()
            st.subheader("👀 Detailed Changes")
            if grouped_diff:
                for group in grouped_diff:
                    with st.expander(f"Employee: {group['Employee']}"):
                        df = pd.DataFrame(group['Changes'])
                        st.table(df)
            else:
                st.info("No differences found between the files.")

        
        with tabs[1]:
            st.subheader("⬇️ Download Reports")
            pdf_new = generate_pdf(grouped_new or [{'Employee': 'N/A', 'Changes': []}], 'new')
            st.download_button("📄 Download PDF (New Joiners)", data=pdf_new, file_name="new_joinees_report.pdf", mime="application/pdf", help="Download new joiners as PDF")

            excel_new_df = flatten_for_excel(grouped_new or [])
            excel_new_buffer = io.BytesIO()
            excel_new_df.to_excel(excel_new_buffer, index=False, engine='openpyxl')
            excel_new_buffer.seek(0)
            st.download_button("📊 Download Excel (New Joiners)", data=excel_new_buffer, file_name="new_joinees_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", help="Download new joiners as Excel")

            st.divider()
            st.subheader("👀 Meet the New Joiners")
            if grouped_new:
                for group in grouped_new:
                    with st.expander(f"Employee: {group['Employee']}"):
                        df = pd.DataFrame(group['Changes'])
                        st.table(df)
            else:
                st.info("No new joiners found in the latest file.")

