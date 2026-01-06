import streamlit as st
import google.genai as genai
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


# ==========================================
# 1. HELPER FUNCTIONS (No Change)
# ==========================================

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


# ==========================================
# 2. PDF GENERATION FUNCTION (No Change)
# ==========================================

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
        separator = "  •  "
        
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
    # This line uses the cleaned data from the Streamlit form
    story.append(Paragraph(separator.join(contact_parts), style_contact))
    
    # 2. Objective
    if data.get('objective'):
        add_section_header("Professional Summary")
        story.append(Paragraph(escape_xml(data.get('objective', '')), style_normal))

    # 3. Experience
    if data.get('experience'):
        add_section_header("Work Experience")
        for job in data.get('experience', []):
            role = escape_xml(job.get('role', ''))
            company = escape_xml(job.get('company', ''))
            dates = escape_xml(job.get('dates', ''))
            
            # --- TEMPLATE SPECIFIC JOB FORMATTING (Rest of Logic is unchanged) ---
            if template_type == "Ivy League":
                add_job_header_table(f"<b>{company}</b>", dates)
                story.append(Paragraph(f"<i>{role}</i>", style_normal))
            elif template_type == "Executive":
                add_job_header_table(f"<b>{company}</b>", f"<b>{dates}</b>")
                story.append(Paragraph(role, style_normal))
            elif template_type == "Classic Serif":
                head = f"<b>{role}</b>, {company} -- <i>{dates}</i>"
                story.append(Paragraph(head, style_normal))
            else: # Modern/Minimalist
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
            p_role = escape_xml(proj.get('role', '')) # New field
            
            if template_type in ["Ivy League", "Executive", "Classic Serif"]:
                head = f"<b>{p_name}</b> [{p_tech}]"
            else:
                head = f"<b>{p_name}</b> | {p_tech}"
            
            story.append(Paragraph(head, style_normal))
            if p_role:
                story.append(Paragraph(f"Role: {p_role}", style_normal))
                
            for b in proj.get('bullets', []): 
                story.append(Paragraph(f"• {escape_xml(b)}", style_bullet))
            story.append(Spacer(1, 8))
            
    # 6. Publications (New Section)
    if data.get('publications'):
        add_section_header("Publications")
        for pub in data.get('publications', []):
            p_title = escape_xml(pub.get('title', ''))
            p_journal = escape_xml(pub.get('journal', ''))
            p_year = escape_xml(pub.get('year', ''))
            
            if p_title:
                head = f"<b>{p_title}</b>"
                story.append(Paragraph(head, style_normal))
            
            detail_line = p_journal
            if p_year: detail_line += f", {p_year}"
            if detail_line:
                story.append(Paragraph(detail_line, style_normal))
            
            story.append(Spacer(1, 6))

    # 7. Skills (No Change)
    if data.get('core_skills'):
        add_section_header("Skills")
        story.append(Paragraph(escape_xml(data.get('core_skills', '')), style_normal))
        
    # 8. Awards & Honors (New Section)
    if data.get('awards'):
        add_section_header("Awards & Honors")
        for award in data.get('awards', []):
            a_name = escape_xml(award.get('name', ''))
            a_year = escape_xml(award.get('year', ''))
            
            if a_name and a_year:
                add_job_header_table(f"<b>{a_name}</b>", a_year)
            elif a_name:
                 story.append(Paragraph(f"<b>{a_name}</b>", style_normal))
            story.append(Spacer(1, 6))
            
    # 9. Scholarship/Fellowship (New Section)
    if data.get('scholarship'):
        add_section_header("Scholarship / Fellowship")
        story.append(Paragraph(escape_xml(data.get('scholarship', '')), style_normal))
        story.append(Spacer(1, 8))

    # 10. Languages (New Section)
    if data.get('languages'):
        add_section_header("Languages")
        story.append(Paragraph(escape_xml(data.get('languages', '')), style_normal))
        story.append(Spacer(1, 8))
        
    # 11. References (New Section - Structured as a table)
    if data.get('references'):
        add_section_header("References")
        
        for ref in data.get('references', []):
            r_name = escape_xml(ref.get('name', ''))
            r_title = escape_xml(ref.get('title', ''))
            r_contact = escape_xml(ref.get('contact', ''))
            
            if r_name:
                 story.append(Paragraph(f"<b>{r_name}</b>", style_normal))
            if r_title:
                 story.append(Paragraph(r_title, style_normal))
            if r_contact:
                 story.append(Paragraph(r_contact, style_normal))
            
            story.append(Spacer(1, 8))


    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==========================================
# 3. STREAMLIT APP (UPDATED DATA PACKAGING)
# ==========================================
st.set_page_config(page_title="Professional Resume Generator", layout="wide")

# --- SKY BACKGROUND CSS (Unchanged) ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-image: url('https://images.unsplash.com/photo-1518066000714-cdcd828ff303?q=80&w=1974&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D'); 
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #333333;
        position: relative;
        overflow: auto;
    }

    [data-testid="stAppViewContainer"]::before {
        content: none !important;
    }
    
    h1, h2, h3, p, label, .stMarkdown, .stSelectbox label {
        color: #1f1f1f !important;
        text-shadow: none;
        font-weight: 600;
    }

    h1 {
        color: #004d40 !important;
    }
    
    .stTextInput input, .stTextArea textarea, .stSelectbox > div {
        background-color: rgba(255, 255, 255, 0.95) !important;
        color: black !important;
        border-radius: 5px;
    }
    
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.5);
        color: #1f1f1f !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📄 Professional Resume Generator")

# --- API KEY HANDLING ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    # Use the key you provided
    API_KEY = "AIzaSyAJURjQpLWGvAbDe9hXOuBk9HopbW4RfcM"

if not API_KEY:
    st.error("⚠️ API Key is missing!")
    st.stop()

# --- INITIALIZE SESSION STATE WITH NEW KEYS ---
if 'resume_data' not in st.session_state: 
    st.session_state.resume_data = {
        "name": "", "address": "", "contact": "", "objective": "", "core_skills": "", 
        "education": [], "experience": [], "projects": [],
        "publications": [], "awards": [], "scholarship": "", 
        "languages": "", "references": [], "MoU": "" # MoU is just text
    }
if 'pdf_bytes' not in st.session_state: st.session_state.pdf_bytes = None

# --- SIDEBAR: SETTINGS & TEMPLATES ---
with st.sidebar:
    st.header("🎨 Template Settings")
    
    template_option = st.selectbox(
        "Select ATS Style",
        ("Ivy League", "Executive", "Classic Serif", "Modern Sans", "Minimalist"),
        help="Ivy League: Centered Serif (Bloomberg). Executive: Bold Left Align (Resume Worded). Modern: Clean Sans."
    )
    
    st.divider()
    
    if st.button("🔄 Reset / New File"):
        st.session_state.resume_data = {
            "name": "", "address": "", "objective": "", "core_skills": "", 
            "education": [], "experience": [], "projects": [],
            "publications": [], "awards": [], "scholarship": "", 
            "languages": "", "references": [], "MoU": ""
        }
        st.session_state.pdf_bytes = None
        st.rerun()

# --- MAIN LOGIC (Extraction) ---
if not st.session_state.resume_data.get('name'):
    st.info("Upload your existing PDF resume to extract data and reformat it.")
    f = st.file_uploader("Upload Resume", type="pdf")
    
    if f and st.button("🔍 Extract & Format"):
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        with st.spinner("Processing..."):
            try:
                raw = extract_text_from_pdf(f)
                man = manual_entity_extraction(raw)
                
                # --- UPDATED PROMPT FOR ALL SECTIONS (Key change for 'contact' clarification)---
                prompt = f"""
                You are an expert Resume Parser. Extract the following details from the resume text into valid JSON format.
                Ensure ALL keys are: "name", "address", "contact", "objective", "core_skills", "education", "experience", "projects", "publications", "awards", "scholarship", "languages", "references", "MoU".
                
                Format rules for keys:
                - contact: A single, comma or pipe-separated string containing ONLY email(s) and phone number(s). DO NOT include structural characters like brackets, quotes, or keywords like 'email:' or 'phone:'.
                - core_skills, scholarship, languages, MoU: Single strings.
                - experience: Array of objects with "company", "role", "dates", "bullets" (list of strings).
                - education: Array of objects with "university", "degree", "year", "grade".
                - projects: Array of objects with "name", "tech", "role" (e.g., PI, Co-I), "bullets".
                - publications: Array of objects with "title", "journal" (includes conference/SCI status), "year".
                - awards: Array of objects with "name", "year".
                - references: Array of objects with "name", "title" (including affiliation), "contact" (email/phone).
                
                Resume Text: {raw}
                """
                
                res = model.generate_content(prompt)
                data = clean_json(res.text)
                
                # Fallback if manual extraction found contact info but AI didn't
                if not data.get('contact'): 
                    data['contact'] = man.get('contact_string', '')
                
                # Ensure contact field is cleaned again in case the LLM returned junk
                if data.get('contact'):
                    data['contact'] = re.sub(r'[\{\}\[\]"\']|email:|phone:', '', data['contact']).strip()
                
                if not data.get('name'): data['name'] = "Name Not Found"
                
                st.session_state.resume_data.update(data)
                
                st.rerun()
            except Exception as e:
                st.error(f"Error during extraction: {e}")

# --- MAIN LOGIC (Editing and Generation) ---
else: 
    st.header("📝 Verify & Edit Data")
    
    with st.form("edit_form"):
        # --- PERSONAL INFO ---
        st.subheader("Personal & Summary")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full Name", st.session_state.resume_data.get('name', ''))
            # --- CONTACT FIELD REMAINS THE FOCUS FOR CLEANING ---
            contact = st.text_input("Contact (Email | Phone)", st.session_state.resume_data.get('contact', ''))
        with c2:
            addr_val = st.session_state.resume_data.get('address', '')
            if addr_val is None: addr_val = ""
            address = st.text_input("Address", value=addr_val, placeholder="City, Country")

        obj = st.text_area("Professional Summary", st.session_state.resume_data.get('objective', ''), height=100)
        
        st.divider()
        
        # --- JSON INPUTS ---
        st.subheader("Core Sections (JSON)")
        c3, c4 = st.columns(2)
        with c3:
            st.markdown("**Experience JSON**")
            exp_json = st.text_area("Experience Data", json.dumps(st.session_state.resume_data.get('experience', []), indent=2), height=300)
            st.markdown("**Publications JSON**")
            pub_json = st.text_area("Publications Data", json.dumps(st.session_state.resume_data.get('publications', []), indent=2), height=300)
        with c4:
            st.markdown("**Education JSON**")
            edu_json = st.text_area("Education Data", json.dumps(st.session_state.resume_data.get('education', []), indent=2), height=150)
            st.markdown("**Projects JSON**")
            proj_json = st.text_area("Projects Data", json.dumps(st.session_state.resume_data.get('projects', []), indent=2), height=150)
            st.markdown("**References JSON**")
            ref_json = st.text_area("References Data", json.dumps(st.session_state.resume_data.get('references', []), indent=2), height=150)

        st.divider()
        
        # --- OTHER SECTIONS ---
        st.subheader("Other Details")
        c5, c6 = st.columns(2)
        with c5:
            skills = st.text_area("Core Skills (Comma Separated)", st.session_state.resume_data.get('core_skills', ''))
            awards_json = st.text_area("Awards JSON", json.dumps(st.session_state.resume_data.get('awards', []), indent=2), height=100)
        with c6:
            scholarship = st.text_area("Scholarship / Fellowship", st.session_state.resume_data.get('scholarship', ''))
            languages = st.text_area("Languages (Comma Separated)", st.session_state.resume_data.get('languages', ''))
        
        mo_u = st.text_area("MoU / Affiliations", st.session_state.resume_data.get('MoU', ''), height=50, help="This is currently treated as a single text block.")

        # GENERATE BUTTON
        if st.form_submit_button("✅ Generate PDF"):
            try:
                # Re-package data from form
                final_data = {
                    "name": name,
                    # --- CLEAN CONTACT DATA BEFORE PASSING TO PDF GENERATOR ---
                    "contact": re.sub(r'[\{\}\[\]"\']|email:|phone:', '', contact).strip(),
                    "address": address,
                    "objective": obj,
                    "core_skills": skills,
                    "education": json.loads(edu_json),
                    "experience": json.loads(exp_json),
                    "projects": json.loads(proj_json),
                    "publications": json.loads(pub_json),
                    "awards": json.loads(awards_json),
                    "scholarship": scholarship,
                    "languages": languages,
                    "references": json.loads(ref_json),
                    "MoU": mo_u
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
