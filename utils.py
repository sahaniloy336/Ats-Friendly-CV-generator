import io
from pypdf import PdfReader
from fpdf import FPDF
import re



def manual_entity_extraction(text):
    """
    Performs Rule-Based NER (Named Entity Recognition) using Regex
    to find Contact Details without using AI.
    """
    data = {}
    
    # 1. Extract EMAIL (Standard Regex pattern)
    # Looks for: characters @ characters . characters
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_match = re.search(email_pattern, text)
    data['email'] = email_match.group(0) if email_match else ""

    # 2. Extract PHONE (Supports various formats)
    # Looks for: 10-12 digits, optionally with + or - or spaces
    # This is a basic pattern; phone regex can get very complex.
    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}'
    phone_match = re.search(phone_pattern, text)
    data['phone'] = phone_match.group(0) if phone_match else ""

    # 3. Extract LINKEDIN (Keyword search)
    # Looks for urls containing 'linkedin.com'
    linkedin_pattern = r'linkedin\.com\/in\/[a-zA-Z0-9_-]+'
    linkedin_match = re.search(linkedin_pattern, text)
    data['linkedin'] = "https://www." + linkedin_match.group(0) if linkedin_match else ""
    
    # Combine them into a contact string
    parts = [data['email'], data['phone'], data['linkedin']]
    # Filter out empty strings and join with " | "
    data['contact_string'] = " | ".join([p for p in parts if p])

    return data

def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        return str(e)

def clean_text(text):
    """Handles special characters for FPDF (Latin-1)"""
    if not isinstance(text, str): return str(text)
    replacements = {
        '\u2013': '-', '\u2014': '--', '\u2018': "'", '\u2019': "'",
        '\u201c': '"', '\u201d': '"', '\u2022': '*', '\u25cf': '*'
    }
    for char, rep in replacements.items():
        text = text.replace(char, rep)
    return text.encode('latin-1', 'replace').decode('latin-1')

class PDF(FPDF):
    def header(self):
        pass

def create_pdf(data):
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)

    # --- 1. HEADER ---
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 8, clean_text(data.get('name', '').upper()), ln=True, align='C')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, clean_text(data.get('contact', '')), ln=True, align='C')
    pdf.ln(5)

    # --- HELPER FUNCTIONS ---
    def section_header(title):
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 6, title.upper(), border='B', ln=True)
        pdf.ln(2)

    def smart_line(left_text, right_text, is_bold=False, is_italic=False):
        """
        Prints left_text and right_text on the same row.
        If left_text is too long, it wraps to the next line WITHOUT overlapping right_text.
        """
        # Set Font Style
        style = ''
        if is_bold: style += 'B'
        if is_italic: style += 'I'
        pdf.set_font('Arial', style, 10)

        # Layout Dimensions
        page_width = pdf.w - pdf.l_margin - pdf.r_margin
        date_width = 45  # Reserved space for Date/Location
        gap = 2
        text_width = page_width - date_width - gap

        # Save starting Y position
        start_y = pdf.get_y()
        
        # 1. Print RIGHT column first (Date/Location)
        pdf.set_x(pdf.w - pdf.r_margin - date_width)
        pdf.cell(date_width, 5, clean_text(right_text), align='R', ln=0)
        
        # 2. Return to LEFT column and print text with wrapping (MultiCell)
        pdf.set_y(start_y) # Go back to the top of the line
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(text_width, 5, clean_text(left_text), align='L')
        
        # Note: multi_cell automatically moves the cursor down. 
        # If the date was somehow taller than the text (unlikely), we'd need to adjust Y,
        # but usually the wrapped text is the tallest element, so the cursor ends up in the right spot.

    def bullet_point(text):
        pdf.set_font('Arial', '', 10)
        pdf.cell(5) # Indent
        pdf.cell(3, 5, "-", ln=0)
        pdf.multi_cell(0, 5, clean_text(text))

    # --- 2. OBJECTIVE ---
    if data.get('objective'):
        section_header("Objective")
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, clean_text(data['objective']))
        pdf.ln(3)

    # --- 3. CORE SKILLS ---
    if data.get('core_skills'):
        section_header("Core Skills")
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, clean_text(data['core_skills']))
        pdf.ln(3)

    # --- 4. EDUCATION ---
    if data.get('education'):
        section_header("Education")
        for edu in data['education']:
            # Line 1: University (Bold) | Location
            smart_line(edu.get('university', ''), edu.get('location', ''), is_bold=True)
            
            # Line 2: Degree (Italic) | Date
            smart_line(edu.get('degree', ''), edu.get('year', ''), is_italic=True)
            
            if edu.get('gpa'):
                pdf.set_font('Arial', '', 10)
                pdf.cell(0, 5, clean_text(f"GPA: {edu['gpa']}"), ln=True)
            pdf.ln(2)

    # --- 5. WORK EXPERIENCE ---
    if data.get('experience'):
        section_header("Work Experience")
        for exp in data['experience']:
            # Line 1: Company (Bold) | Location
            smart_line(exp.get('company', ''), exp.get('location', ''), is_bold=True)
            
            # Line 2: Role (Italic) | Dates
            smart_line(exp.get('role', ''), exp.get('dates', ''), is_italic=True)
            
            for bullet in exp.get('bullets', []):
                bullet_point(bullet)
            pdf.ln(2)

    # --- 6. PROJECTS ---
    if data.get('projects'):
        section_header("Project Work")
        for proj in data['projects']:
            # Line 1: Name (Bold) | Date
            smart_line(proj.get('name', ''), proj.get('dates', ''), is_bold=True)
            
            if proj.get('tech'):
                pdf.set_font('Arial', 'I', 10)
                pdf.cell(0, 5, clean_text(f"Tech: {proj['tech']}"), ln=True)
            
            for bullet in proj.get('bullets', []):
                bullet_point(bullet)
            pdf.ln(2)

    # --- 7. OTHER SKILLS ---
    if data.get('other_skills'):
        section_header("Other Skills")
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, clean_text(data['other_skills']))
    
    return pdf.output(dest='S').encode('latin-1', errors='replace')