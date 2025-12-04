import streamlit as st
import google.generativeai as genai
import json
import re
import io

# --- LIBRARIES ---
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Flowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from pdfminer.high_level import extract_text



def extract_text_from_pdf(uploaded_file):
    return extract_text(uploaded_file)

def manual_entity_extraction(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    phones = re.findall(phone_pattern, text)
    contact_string = " | ".join(emails[:1] + phones[:1])
    return {"contact_string": contact_string}

def clean_json(text):
    try:
        text = text.replace("```json", "").replace("```", "")
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: text = match.group(0)
        return json.loads(text)
    except:
        return {}

def escape_xml(text):
    """Escapes special characters that crash ReportLab."""
    if not text: return ""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

def calculate_percentage(grade_str):
    if not grade_str: return None
    if "%" in str(grade_str): return None
    match = re.search(r'(\d+(\.\d+)?)\s*/\s*(\d+(\.\d+)?)', str(grade_str))
    if match:
        try:
            obtained = float(match.group(1))
            total = float(match.group(3))
            if total > 0: return f"{(obtained / total) * 100:.1f}%"
        except: pass
    return None

# --- CUSTOM LINE DRAWING ---
class MCLine(Flowable):
    def __init__(self, width, height=0):
        Flowable.__init__(self)
        self.width = width
        self.height = height
    def draw(self):
        self.canv.setLineWidth(1)
        self.canv.setStrokeColor(colors.black)
        self.canv.line(0, 0, self.width, 0)


def create_pdf(data, template_type):
    buffer = io.BytesIO()
    
    
    if template_type == "Classic Serif":
        font_header = "Times-Bold"
        font_body = "Times-Roman"
        header_align = TA_CENTER
        name_size = 24
        section_header_case = "title" 
        has_lines = True
        separator = " | "
        
    elif template_type == "Modern Sans":
        font_header = "Helvetica-Bold"
        font_body = "Helvetica"
        header_align = TA_LEFT
        name_size = 26
        section_header_case = "upper" 
        has_lines = False 
        separator = "  •  "
        
    elif template_type == "Minimalist":
        font_header = "Helvetica-Bold"
        font_body = "Helvetica"
        header_align = TA_LEFT
        name_size = 20
        section_header_case = "upper"
        has_lines = True
        separator = " | "

    elif template_type == "Ivy League": 
        font_header = "Times-Bold"
        font_body = "Times-Roman"
        header_align = TA_CENTER
        name_size = 26
        section_header_case = "title" 
        has_lines = True
        separator = " • "
        
    elif template_type == "Executive": 
        font_header = "Times-Bold"
        font_body = "Times-Roman"
        header_align = TA_LEFT
        name_size = 28
        section_header_case = "upper" 
        has_lines = True
        separator = " | "
        
    else: # Fallback
        font_header = "Helvetica-Bold"
        font_body = "Helvetica"
        header_align = TA_LEFT
        name_size = 22
        section_header_case = "title"
        has_lines = True
        separator = " | "


    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                            rightMargin=40, leftMargin=40, 
                            topMargin=40, bottomMargin=40)
    story = [] 
    styles = getSampleStyleSheet()
    full_width = 530 

    # Define Dynamic Paragraph Styles
    style_name = ParagraphStyle('Name', parent=styles['Normal'], 
                                fontSize=name_size, alignment=header_align, 
                                spaceAfter=6, fontName=font_header, leading=name_size+4)
    
    style_contact = ParagraphStyle('Contact', parent=styles['Normal'], 
                                   fontSize=10, alignment=header_align, 
                                   spaceAfter=10, fontName=font_body, leading=12)
    
    style_header = ParagraphStyle('Header', parent=styles['Normal'], 
                                  fontSize=12, spaceBefore=12, spaceAfter=4, 
                                  fontName=font_header, alignment=TA_LEFT)
    
    style_normal = ParagraphStyle('Normal_Body', parent=styles['Normal'], 
                                  fontSize=10.5, leading=14, alignment=TA_LEFT, fontName=font_body)
    
    style_bullet = ParagraphStyle('Bullet_Body', parent=styles['Normal'], 
                                  fontSize=10.5, leading=14, leftIndent=15, bulletIndent=0, fontName=font_body)
    
    # Styles specifically for the "Table" headers (Right aligned dates)
    style_left_col = ParagraphStyle('LeftCol', parent=styles['Normal'], fontSize=10.5, leading=14, fontName=font_body)
    style_right_col = ParagraphStyle('RightCol', parent=styles['Normal'], fontSize=10.5, leading=14, fontName=font_body, alignment=TA_RIGHT)

    # --- HELPER FOR SECTIONS ---
    def add_section_header(text):
        if section_header_case == "upper":
            text = text.upper()
        story.append(Paragraph(text, style_header))
        if has_lines:
            story.append(MCLine(full_width))
            story.append(Spacer(1, 8))

    # --- HELPER FOR JOB HEADERS (TABLE BASED) ---
    def add_job_header_table(left_text, right_text):
        # Create a 2-column table: Left text (Company) | Right text (Date)
        # This ensures the date is always perfectly right-aligned
        data_row = [[Paragraph(left_text, style_left_col), Paragraph(right_text, style_right_col)]]
        t = Table(data_row, colWidths=[full_width * 0.75, full_width * 0.25])
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(t)

    # --- BUILD CONTENT ---
    
    # 1. Name & Contact
    name = escape_xml(data.get('name', 'Name Not Provided'))
    story.append(Paragraph(name, style_name))
    
    contact_parts = []
    if data.get('address'): contact_parts.append(escape_xml(data.get('address')))
    if data.get('contact'): contact_parts.append(escape_xml(data.get('contact')))
    story.append(Paragraph(separator.join(contact_parts), style_contact))
    
    # 2. Objective
    if data.get('objective'):
        add_section_header("Professional Summary")
        story.append(Paragraph(escape_xml(data.get('objective', '')), style_normal))

    # 3. Experience
    if data.get('experience'):
        add_section_header("Experience")
        for job in data.get('experience', []):
            role = escape_xml(job.get('role', ''))
            company = escape_xml(job.get('company', ''))
            dates = escape_xml(job.get('dates', ''))
            
            # --- TEMPLATE SPECIFIC JOB FORMATTING ---
            if template_type == "Ivy League":
                # Table: Company (Left) | Dates (Right)
                # Next Line: Role (Italic)
                add_job_header_table(f"<b>{company}</b>", dates)
                story.append(Paragraph(f"<i>{role}</i>", style_normal))
                
            elif template_type == "Executive":
                # Table: Company (Bold) | Dates (Bold, Right)
                # Next Line: Role
                add_job_header_table(f"<b>{company}</b>", f"<b>{dates}</b>")
                story.append(Paragraph(role, style_normal))
                
            elif template_type == "Classic Serif":
                # Single Line: Role, Company -- Dates
                head = f"<b>{role}</b>, {company} -- <i>{dates}</i>"
                story.append(Paragraph(head, style_normal))
            
            else: # Modern/Minimalist
                # Single Line: Role | Company (Dates)
                head = f"<b>{role}</b> | {company} <font color='grey' size=9>({dates})</font>"
                story.append(Paragraph(head, style_normal))
            
            for b in job.get('bullets', []): 
                story.append(Paragraph(f"• {escape_xml(b)}", style_bullet))
            story.append(Spacer(1, 10))

    # 4. Education
    if data.get('education'):
        add_section_header("Education")
        for edu in data.get('education', []):
            degree = escape_xml(edu.get('degree', ''))
            uni = escape_xml(edu.get('university', ''))
            year = escape_xml(edu.get('year', ''))
            grade = escape_xml(edu.get('grade', ''))
            
            if template_type == "Ivy League" or template_type == "Executive":
                # Table: University (Left) | Year (Right)
                # Next Line: Degree
                add_job_header_table(f"<b>{uni}</b>", year)
                story.append(Paragraph(degree, style_normal))
            else:
                line = f"<b>{degree}</b>, {uni}"
                if year: line += f", {year}"
                story.append(Paragraph(line, style_normal))

            if grade:
                pct = calculate_percentage(grade)
                g_txt = f"Grade: {grade} ({pct})" if pct else f"Grade: {grade}"
                story.append(Paragraph(g_txt, style_normal))
            story.append(Spacer(1, 8))

    # 5. Projects
    if data.get('projects'):
        add_section_header("Projects")
        for proj in data.get('projects', []):
            p_name = escape_xml(proj.get('name', ''))
            p_tech = escape_xml(proj.get('tech', ''))
            
            if template_type in ["Ivy League", "Executive", "Classic Serif"]:
                head = f"<b>{p_name}</b> [{p_tech}]"
            else:
                head = f"<b>{p_name}</b> | {p_tech}"
                
            story.append(Paragraph(head, style_normal))
            for b in proj.get('bullets', []): 
                story.append(Paragraph(f"• {escape_xml(b)}", style_bullet))
            story.append(Spacer(1, 8))
            
    # 6. Skills
    if data.get('core_skills'):
        add_section_header("Skills")
        story.append(Paragraph(escape_xml(data.get('core_skills', '')), style_normal))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==========================================
# 3. STREAMLIT APP
# ==========================================
st.set_page_config(page_title="Professional Resume Generator", layout="wide")

# --- ANIMATED BACKGROUND CSS ---
st.markdown("""
<style>
    /* Gradient Animation */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(-45deg, #0f2027, #203a43, #2c5364, #24243e);
        background-size: 400% 400%;
        animation: gradientBG 15s ease infinite;
        color: white;
    }
    
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* Make text readable on dark background */
    h1, h2, h3, p, label, .stMarkdown {
        color: white !important;
        text-shadow: 1px 1px 2px black;
    }
    
    /* Style the input fields to pop out */
    .stTextInput input, .stTextArea textarea {
        background-color: rgba(255, 255, 255, 0.95) !important;
        color: black !important;
        border-radius: 5px;
    }
    
    /* Sidebar adjustments */
    [data-testid="stSidebar"] {
        background-color: rgba(0, 0, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.title("📄 Professional Resume Generator")

# --- API KEY HANDLING ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    # Use the key you provided
    API_KEY = "Enter your API key here"

if not API_KEY:
    st.error("⚠️ API Key is missing!")
    st.stop()

if 'resume_data' not in st.session_state: st.session_state.resume_data = None
if 'pdf_bytes' not in st.session_state: st.session_state.pdf_bytes = None

# --- SIDEBAR: SETTINGS & TEMPLATES ---
with st.sidebar:
    st.header("🎨 Template Settings")
    
    # --- TEMPLATE SELECTOR ---
    template_option = st.selectbox(
        "Select ATS Style",
        ("Ivy League", "Executive", "Classic Serif", "Modern Sans", "Minimalist"),
        help="Ivy League: Centered Serif (Bloomberg). Executive: Bold Left Align (Resume Worded). Modern: Clean Sans."
    )
    
    st.divider()
    
    if st.button("🔄 Reset / New File"):
        st.session_state.resume_data = None
        st.session_state.pdf_bytes = None
        st.rerun()

# --- MAIN LOGIC ---
if not st.session_state.resume_data:
    st.info("Upload your existing PDF resume to extract data and reformat it.")
    f = st.file_uploader("Upload Resume", type="pdf")
    if f and st.button("🔍 Extract & Format"):
        genai.configure(api_key=API_KEY)
        
        # --- USING GEMINI 2.5 FLASH ---
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        with st.spinner("Processing..."):
            try:
                raw = extract_text_from_pdf(f)
                man = manual_entity_extraction(raw)
                
                prompt = f"""
                You are an expert Resume Parser. Extract the following details from the resume text into valid JSON format.
                Ensure keys are: "name", "address", "objective", "core_skills", "education", "experience", "projects".
                
                Format rules:
                - core_skills: A single string with skills separated by commas.
                - experience: Array of objects with "company", "role", "dates", "bullets" (list of strings).
                - education: Array of objects with "university", "degree", "year", "grade".
                - projects: Array of objects with "name", "tech", "bullets".
                
                Resume Text: {raw}
                """
                
                res = model.generate_content(prompt)
                data = clean_json(res.text)
                
                # Fallback if manual extraction found contact info but AI didn't
                if not data.get('contact'): data['contact'] = man.get('contact_string', '')
                if not data.get('name'): data['name'] = "Name Not Found"
                
                st.session_state.resume_data = data
                st.rerun()
            except Exception as e:
                st.error(f"Error during extraction: {e}")

else:
    st.header("📝 Verify & Edit Data")
    
    with st.form("edit_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full Name", st.session_state.resume_data.get('name', ''))
            contact = st.text_input("Contact (Email | Phone)", st.session_state.resume_data.get('contact', ''))
        with c2:
            addr_val = st.session_state.resume_data.get('address', '')
            if addr_val is None: addr_val = ""
            address = st.text_input("Address", value=addr_val, placeholder="City, Country")

        obj = st.text_area("Professional Summary", st.session_state.resume_data.get('objective', ''), height=100)
        skills = st.text_area("Skills (Comma Separated)", st.session_state.resume_data.get('core_skills', ''))

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**Experience JSON**")
            exp_json = st.text_area("Experience Data", json.dumps(st.session_state.resume_data.get('experience', []), indent=2), height=300)
        with c4:
            st.markdown("**Education JSON**")
            edu_json = st.text_area("Education Data", json.dumps(st.session_state.resume_data.get('education', []), indent=2), height=150)
            st.markdown("**Projects JSON**")
            proj_json = st.text_area("Projects Data", json.dumps(st.session_state.resume_data.get('projects', []), indent=2), height=150)

        # GENERATE BUTTON
        if st.form_submit_button("✅ Generate PDF"):
            try:
                # Re-package data from form
                final_data = {
                    "name": name,
                    "contact": contact,
                    "address": address,
                    "objective": obj,
                    "core_skills": skills,
                    "education": json.loads(edu_json),
                    "experience": json.loads(exp_json),
                    "projects": json.loads(proj_json)
                }
                
                # CALL CREATOR WITH SELECTED TEMPLATE
                st.session_state.pdf_bytes = create_pdf(final_data, template_option)
                
            except Exception as e:
                st.error(f"Error generating PDF: {e}")

    # DOWNLOAD BUTTON
    if st.session_state.pdf_bytes:
        st.success(f"Template Ready: {template_option}")
        st.download_button(
            label="📥 Download PDF", 
            data=st.session_state.pdf_bytes, 
            file_name=f"Professional_Resume_{template_option.replace(' ', '_')}.pdf", 
            mime="application/pdf"
        )