"""Generate fictional resumes (PDF and DOCX) and candidate metadata.

Single source of truth is CANDIDATES in scripts.candidate_data.
Does NOT modify or overwrite data/test_dataset/ground_truth.json.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Add project root to path so scripts can be run from anywhere
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.candidate_data import CANDIDATES

DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def get_chrome_path() -> str:
    path = os.environ.get("CHROME_PATH", DEFAULT_CHROME_PATH)
    if not Path(path).is_file():
        raise RuntimeError(
            f"Google Chrome not found at '{path}'. "
            "Install Google Chrome or set the CHROME_PATH environment variable."
        )
    return path


def build_candidates_metadata() -> list[dict]:
    """Extract metadata schema from CANDIDATES profiles."""
    metadata = []
    for c in CANDIDATES:
        metadata.append(
            {
                "candidate_id": c["candidate_id"],
                "file_name": c["file_name"],
                "format": c["format"],
                "layout": c["layout"],
                "docx_heading_style": c["docx_heading_style"],
                "total_experience_years": c["total_experience_years"],
                "skills": c["skills"],
            }
        )
    return metadata


def render_html(candidate: dict) -> str:
    """Render a candidate profile into an HTML document with real-world styling."""
    c = candidate
    layout = c["layout"]

    # Filter skills for display in the Skills section (omit project_only skills)
    visible_skills = [s for s in c["skills"] if s.get("location") != "project_only"]

    skills_bullets = "".join(f"<li style='margin-bottom: 4px;'><strong>{s['name']}</strong> &mdash; {s['years']} yrs</li>" for s in visible_skills)

    # 2-column skills grid for corporate layout
    half = (len(visible_skills) + 1) // 2
    col1_skills = visible_skills[:half]
    col2_skills = visible_skills[half:]
    col1_html = "".join(f"<li style='margin-bottom: 4px;'><strong>{s['name']}</strong> ({s['years']} yrs)</li>" for s in col1_skills)
    col2_html = "".join(f"<li style='margin-bottom: 4px;'><strong>{s['name']}</strong> ({s['years']} yrs)</li>" for s in col2_skills)

    skills_table_rows = "".join(
        f"<tr><td style='padding: 6px 12px; font-weight: 600;'>{s['name']}</td><td style='padding: 6px 12px;'>{s['years']} years</td></tr>"
        for s in visible_skills
    )

    roles_html = ""
    for r in c["roles"]:
        bullets_html = "".join(f"<li style='margin-bottom: 6px;'>{b}</li>" for b in r["bullets"])
        roles_html += f"""
        <div class="role" style="margin-bottom: 18px;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 3px;">
            <tr>
              <td style="font-weight: bold; font-size: 15px; color: #1a365d;">{r['title']}</td>
              <td align="right" style="font-size: 13px; font-weight: 600; color: #4a5568;">{r['start_date']} &ndash; {r['end_date']}</td>
            </tr>
            <tr>
              <td colspan="2" style="font-size: 13px; color: #4a5568; font-style: italic; padding-bottom: 6px;">{r['company']} &bull; {c['location']}</td>
            </tr>
          </table>
          <ul style="margin: 0; padding-left: 20px; font-size: 13.5px; line-height: 1.45; color: #2d3748;">
            {bullets_html}
          </ul>
        </div>
        """

    base_style = """
      body { font-family: Arial, Helvetica, sans-serif;
             margin: 36px 42px; color: #2d3748; font-size: 13.5px; line-height: 1.45; }
      h1 { margin: 0 0 6px 0; font-size: 24px; color: #1a202c; letter-spacing: 0.5px; }
      h2.sec-head { margin: 18px 0 8px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;
                    border-bottom: 1.5px solid #cbd5e0; padding-bottom: 4px; color: #2b6cb0; font-weight: bold; }
      .contact-bar { color: #4a5568; font-size: 12.5px; margin-bottom: 12px; }
      table.data-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 13px; }
      table.data-table th { background: #edf2f7; color: #2d3748; padding: 7px 12px; text-align: left; border: 1px solid #cbd5e0; font-size: 12.5px; }
      table.data-table td { border: 1px solid #e2e8f0; }
      table.data-table tr:nth-child(even) { background: #f7fafc; }
      .badge-head { background: #2b6cb0; color: #ffffff; padding: 4px 8px; font-size: 11px;
                    font-weight: bold; letter-spacing: 1px; text-transform: uppercase; border-radius: 2px;
                    margin: 16px 0 8px 0; display: inline-block; }
    """

    if layout == "single_column":
        # Classic Corporate layout (prominent name, divider, 2-column skills block, detailed experience)
        content = f"""
          <div style="text-align: center; margin-bottom: 18px;">
            <h1 style="font-size: 26px; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 4px;">{c['name']}</h1>
            <div style="font-size: 14px; font-weight: 600; color: #2b6cb0; margin-bottom: 6px;">{c['title']}</div>
            <div class="contact-bar">{c['location']} &bull; {c['phone']} &bull; {c['email']}</div>
            <hr style="border: 0; border-top: 1.5px solid #2d3748; margin: 10px auto 0 auto;">
          </div>

          <h2 class="sec-head">Professional Summary</h2>
          <p style="margin-top: 4px; margin-bottom: 14px; color: #2d3748;">{c['summary']}</p>

          <h2 class="sec-head">Core Competencies & Technical Skills</h2>
          <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 14px;">
            <tr>
              <td width="50%" valign="top">
                <ul style="margin: 0; padding-left: 18px;">{col1_html}</ul>
              </td>
              <td width="50%" valign="top">
                <ul style="margin: 0; padding-left: 18px;">{col2_html}</ul>
              </td>
            </tr>
          </table>

          <h2 class="sec-head">Professional Experience</h2>
          {roles_html}

          <h2 class="sec-head">Education & Credentials</h2>
          <p style="margin-top: 4px; font-weight: 500;">{c['education']}</p>
        """
    elif layout == "table":
        # Technical Matrix layout (skill table with levels/tenure, structured sections)
        content = f"""
          <div style="border-bottom: 2px solid #2b6cb0; padding-bottom: 12px; margin-bottom: 18px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td>
                  <h1 style="color: #1a365d; font-size: 26px; margin: 0;">{c['name']}</h1>
                  <div style="font-size: 14px; font-weight: 600; color: #2b6cb0; margin-top: 2px;">{c['title']}</div>
                </td>
                <td align="right" valign="bottom" class="contact-bar" style="margin: 0;">
                  {c['location']}<br>{c['phone']} &bull; {c['email']}
                </td>
              </tr>
            </table>
          </div>

          <h2 class="sec-head">Executive Summary</h2>
          <p style="margin-top: 4px; margin-bottom: 16px;">{c['summary']}</p>

          <h2 class="sec-head">Technical Proficiency Matrix</h2>
          <table class="data-table">
            <thead>
              <tr><th width="50%">Core Competency</th><th width="50%">Verified Experience</th></tr>
            </thead>
            <tbody>
              {skills_table_rows}
            </tbody>
          </table>

          <h2 class="sec-head">Work History & Key Projects</h2>
          {roles_html}

          <h2 class="sec-head">Academic Background</h2>
          <p style="margin-top: 4px;">{c['education']}</p>
        """
    else:  # two_column
        # Modern Sidebar layout (left accent panel with badges, right experience flow)
        content = f"""
          <div style="background: #1a365d; color: #ffffff; padding: 20px 24px; border-radius: 4px; margin-bottom: 22px;">
            <h1 style="color: #ffffff; margin: 0; font-size: 26px;">{c['name']}</h1>
            <div style="color: #90cdf4; font-size: 14px; font-weight: 600; margin-top: 4px;">{c['title']}</div>
            <div style="color: #e2e8f0; font-size: 12.5px; margin-top: 6px;">{c['location']} &bull; {c['phone']} &bull; {c['email']}</div>
          </div>

          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td width="33%" valign="top" style="padding-right: 28px; border-right: 1px solid #e2e8f0;">
                <div class="badge-head" style="margin-top: 0;">Core Skills</div>
                <ul style="margin: 0 0 16px 0; padding-left: 18px; font-size: 13px;">{skills_bullets}</ul>

                <div class="badge-head">Education</div>
                <p style="margin: 4px 0 16px 0; font-size: 12.5px; line-height: 1.4;">{c['education']}</p>
              </td>
              <td width="67%" valign="top" style="padding-left: 28px;">
                <h2 class="sec-head" style="margin-top: 0;">Professional Summary</h2>
                <p style="margin-top: 4px; margin-bottom: 18px;">{c['summary']}</p>

                <h2 class="sec-head">Work Experience</h2>
                {roles_html}
              </td>
            </tr>
          </table>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{c['name']} - Resume</title>
  <style>{base_style}</style>
</head>
<body>
  {content}
</body>
</html>"""


def generate_pdf(candidate: dict, output_path: Path, chrome_path: str) -> None:
    """Render a candidate profile to PDF using Chrome headless."""
    html_content = render_html(candidate)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        html_file = tmp_path / "resume.html"
        html_file.write_text(html_content, encoding="utf-8")
        user_data_dir = tmp_path / "chrome_user_data"
        user_data_dir.mkdir()

        cmd = [
            chrome_path,
            "--headless=new",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data_dir}",
            f"--print-to-pdf={output_path}",
            f"file://{html_file.resolve()}",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Chrome failed to render {candidate['file_name']}: {res.stderr}")


def generate_docx(candidate: dict, output_path: Path) -> None:
    """Render a candidate profile to DOCX using python-docx."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor

    doc = Document()
    c = candidate
    layout = c["layout"]
    use_true_headings = c["docx_heading_style"] == "true_headings"

    # Adjust page margins
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)

    def add_section_header(title: str, target_doc=doc):
        if use_true_headings:
            if hasattr(target_doc, "add_heading"):
                return target_doc.add_heading(title, level=1)
            else:
                return target_doc.add_paragraph(title, style="Heading 1")
        p = target_doc.add_paragraph()
        r = p.add_run(title)
        r.bold = True
        r.font.size = Pt(13)
        r.font.color.rgb = RGBColor(34, 34, 34)
        return p

    def add_roles(target_doc):
        for r in c["roles"]:
            p = target_doc.add_paragraph()
            r_title = p.add_run(f"{r['title']} — {r['company']}\n")
            r_title.bold = True
            r_dates = p.add_run(f"{r['start_date']} to {r['end_date']}")
            r_dates.font.size = Pt(9.5)
            r_dates.font.color.rgb = RGBColor(100, 100, 100)

            for b in r["bullets"]:
                target_doc.add_paragraph(b, style="List Bullet")

    visible_skills = [s for s in c["skills"] if s.get("location") != "project_only"]

    # Header
    p_name = doc.add_paragraph()
    r_name = p_name.add_run(c["name"])
    r_name.bold = True
    r_name.font.size = Pt(20)

    p_title = doc.add_paragraph()
    r_t = p_title.add_run(c["title"])
    r_t.bold = True
    r_t.font.size = Pt(12)

    p_contact = doc.add_paragraph()
    p_contact.add_run(f"{c['email']}  •  {c['phone']}  •  {c['location']}")

    if layout == "two_column":
        # 1-row, 2-column Word table
        table = doc.add_table(rows=1, cols=2)
        cell_sidebar = table.cell(0, 0)
        cell_main = table.cell(0, 1)

        # Sidebar content
        add_section_header("Core Skills", cell_sidebar)
        for s in visible_skills:
            cell_sidebar.add_paragraph(f"{s['name']} ({s['years']} yrs)", style="List Bullet")

        add_section_header("Education", cell_sidebar)
        cell_sidebar.add_paragraph(c["education"])

        # Main content
        add_section_header("Professional Summary", cell_main)
        cell_main.add_paragraph(c["summary"])

        add_section_header("Work Experience", cell_main)
        add_roles(cell_main)

    elif layout == "table":
        add_section_header("Professional Summary")
        doc.add_paragraph(c["summary"])

        add_section_header("Core Technical Skills")
        skill_table = doc.add_table(rows=len(visible_skills) + 1, cols=2)
        hdr_cells = skill_table.rows[0].cells
        hdr_cells[0].paragraphs[0].add_run("Skill").bold = True
        hdr_cells[1].paragraphs[0].add_run("Experience").bold = True

        for idx, s in enumerate(visible_skills, start=1):
            row_cells = skill_table.rows[idx].cells
            row_cells[0].text = s["name"]
            row_cells[1].text = f"{s['years']} years"

        add_section_header("Work Experience")
        add_roles(doc)

        add_section_header("Education")
        doc.add_paragraph(c["education"])

    else:  # single_column
        add_section_header("Professional Summary")
        doc.add_paragraph(c["summary"])

        add_section_header("Core Technical Skills")
        for s in visible_skills:
            doc.add_paragraph(f"{s['name']} ({s['years']} yrs)", style="List Bullet")

        add_section_header("Work Experience")
        add_roles(doc)

        add_section_header("Education")
        doc.add_paragraph(c["education"])

    doc.save(output_path)


def generate_all(
    dataset_dir: Path | None = None,
    chrome_path: str | None = None,
) -> tuple[Path, Path]:
    """
    Generate candidates_metadata.json and all 30 resume files.
    Does NOT touch ground_truth.json.
    """
    if dataset_dir is None:
        dataset_dir = PROJECT_ROOT / "data" / "test_dataset"
    if chrome_path is None:
        chrome_path = get_chrome_path()

    dataset_dir.mkdir(parents=True, exist_ok=True)
    resumes_dir = dataset_dir / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write candidates_metadata.json
    metadata = build_candidates_metadata()
    metadata_path = dataset_dir / "candidates_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    # 2. Render resumes
    for c in CANDIDATES:
        out_path = resumes_dir / c["file_name"]
        if c["format"] == "pdf":
            generate_pdf(c, out_path, chrome_path)
        else:
            generate_docx(c, out_path)

    return metadata_path, resumes_dir


def main() -> None:
    print("Generating test resumes and candidates metadata...")
    chrome_path = get_chrome_path()
    meta_path, resumes_dir = generate_all(chrome_path=chrome_path)
    count = len(list(resumes_dir.glob("*")))
    print(f"Generated {count} resume files in {resumes_dir}")
    print(f"Wrote metadata to {meta_path}")


if __name__ == "__main__":
    main()
