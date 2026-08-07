from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "ALMOND_Installation_Manual.pdf"
ONEDRIVE_URL = (
    "https://unsw-my.sharepoint.com/:f:/g/personal/"
    "z5462057_ad_unsw_edu_au/IgCDusTbCoy4TIvZjFGzW6nFAUVNNinwLIUlanldfyHryZs?e=zckK4M"
)
ARCHIVE = "deepwukong-rtx5060-cu128-experimental.tar"
CHECKSUM = "0482EA09F89569072427344B1DADA5E72878DF2E7BC99F878F5895B17DAF6B1D"

NAVY = colors.HexColor("#172554")
BLUE = colors.HexColor("#2563EB")
CYAN = colors.HexColor("#0891B2")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#5B6475")
PALE = colors.HexColor("#EFF6FF")
LINE = colors.HexColor("#D7DFEA")
CODE_BG = colors.HexColor("#111827")
CODE_FG = colors.HexColor("#E2E8F0")


def fonts() -> tuple[str, str, str]:
    regular = Path(r"C:\Windows\Fonts\arial.ttf")
    bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
    mono = Path(r"C:\Windows\Fonts\consola.ttf")
    if regular.exists() and bold.exists() and mono.exists():
        pdfmetrics.registerFont(TTFont("ManualSans", str(regular)))
        pdfmetrics.registerFont(TTFont("ManualSans-Bold", str(bold)))
        pdfmetrics.registerFont(TTFont("ManualMono", str(mono)))
        return "ManualSans", "ManualSans-Bold", "ManualMono"
    return "Helvetica", "Helvetica-Bold", "Courier"


FONT, FONT_BOLD, FONT_MONO = fonts()
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleWhite", fontName=FONT_BOLD, fontSize=31, leading=36, textColor=colors.white))
styles.add(ParagraphStyle(name="SubtitleWhite", fontName=FONT, fontSize=13, leading=19, textColor=colors.HexColor("#DBEAFE")))
styles.add(ParagraphStyle(name="CoverMeta", fontName=FONT, fontSize=8.5, leading=11, textColor=colors.HexColor("#DBEAFE")))
styles.add(ParagraphStyle(name="Section", fontName=FONT_BOLD, fontSize=18, leading=22, textColor=NAVY, spaceAfter=4 * mm))
styles.add(ParagraphStyle(name="Subsection", fontName=FONT_BOLD, fontSize=11.5, leading=15, textColor=BLUE, spaceBefore=3 * mm, spaceAfter=2 * mm))
styles.add(ParagraphStyle(name="BodyManual", fontName=FONT, fontSize=9.5, leading=14, textColor=INK, spaceAfter=2.5 * mm))
styles.add(ParagraphStyle(name="Small", fontName=FONT, fontSize=8, leading=11, textColor=MUTED))
styles.add(ParagraphStyle(name="BulletManual", fontName=FONT, fontSize=9.5, leading=14, textColor=INK, leftIndent=5 * mm, firstLineIndent=-3.5 * mm, bulletIndent=1.5 * mm, spaceAfter=1.5 * mm))
styles.add(ParagraphStyle(name="CodeManual", fontName=FONT_MONO, fontSize=8.2, leading=11.5, textColor=CODE_FG))
styles.add(ParagraphStyle(name="CalloutText", fontName=FONT, fontSize=9.3, leading=13.5, textColor=INK))


def p(text: str, style: str = "BodyManual") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet(text: str) -> Paragraph:
    return Paragraph(f"<bullet>-</bullet>{text}", styles["BulletManual"])


def code(text: str) -> Table:
    content = Preformatted(text.strip("\n"), styles["CodeManual"])
    table = Table([[content]], colWidths=[168 * mm], hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#334155")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
    ]))
    table.spaceBefore = 1.5 * mm
    table.spaceAfter = 3.5 * mm
    return table


def callout(text: str) -> Table:
    table = Table([[p(text, "CalloutText")]], colWidths=[168 * mm], hAlign="CENTER")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#93C5FD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    table.spaceBefore = 1.5 * mm
    table.spaceAfter = 3.5 * mm
    return table


def info_table(rows: list[tuple[str, str]], left: float = 46 * mm) -> Table:
    data = [[p(f"<b>{label}</b>"), p(value)] for label, value in rows]
    table = Table(data, colWidths=[left, 168 * mm - left], hAlign="CENTER")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
    ]))
    return table


def footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    if doc.page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(BLUE)
        canvas.rect(0, height - 13 * mm, width, 13 * mm, fill=1, stroke=0)
        canvas.setFillColor(CYAN)
        canvas.rect(0, 0, 12 * mm, height, fill=1, stroke=0)
    else:
        canvas.setFillColor(BLUE)
        canvas.rect(0, height - 5 * mm, width, 5 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(LINE)
        canvas.line(20 * mm, 15 * mm, width - 20 * mm, 15 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 7.5)
        canvas.drawString(20 * mm, 10.5 * mm, "ALMOND Installation Manual | 2026 T2")
        canvas.drawRightString(width - 20 * mm, 10.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def story() -> list:
    items: list = []
    items += [
        Spacer(1, 34 * mm),
        p("ALMOND", "TitleWhite"),
        Spacer(1, 4 * mm),
        p("DeepWuKong Robustness Experiment System", "SubtitleWhite"),
        Spacer(1, 18 * mm),
        p("INSTALLATION MANUAL", "TitleWhite"),
        Spacer(1, 4 * mm),
        p("Verified Docker delivery, GPU setup, build, test, launch, and troubleshooting instructions.", "SubtitleWhite"),
        Spacer(1, 25 * mm),
        Table(
            [
                [p("SUBMISSION", "CoverMeta"), p("2026 Term 2", "CoverMeta")],
                [p("PLATFORM", "CoverMeta"), p("Windows + Docker Desktop + NVIDIA GPU", "CoverMeta")],
                [p("DOCUMENT VERSION", "CoverMeta"), p("1.1 | 7 August 2026", "CoverMeta")],
            ],
            colWidths=[45 * mm, 95 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1E3A8A")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#60A5FA")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]),
        ),
        Spacer(1, 22 * mm),
        p("Use this manual with the source-code submission and the verified UNSW OneDrive Docker delivery folder.", "SubtitleWhite"),
        PageBreak(),
    ]

    items += [
        p("1  Installation overview", "Section"),
        p("ALMOND measures the robustness of the DeepWuKong CWE-119 vulnerability detector under controlled source-code and program-graph perturbations."),
        p("Installation map", "Subsection"),
        info_table([
            ("Step 1", "Install and start Docker Desktop using Linux containers and the WSL 2 backend."),
            ("Step 2", "Confirm that Docker can access a supported NVIDIA GPU."),
            ("Step 3", "Download, verify, and load the DeepWuKong runtime TAR from UNSW OneDrive."),
            ("Step 4", "Extract the ALMOND source-code ZIP to a writable Windows directory."),
            ("Step 5", "Build the project image and run all 66 container tests."),
            ("Step 6", "Start ALMOND with Start.exe or robustness_experiments\\Start.ps1."),
        ]),
        Spacer(1, 4 * mm),
        p("Included in the source submission", "Subsection"),
        bullet("Project source, Windows launcher, Docker definition, tests, input samples, checkpoint, dashboards, and representative evidence."),
        bullet("The Docker runtime archive is not stored in Git or inside the Moodle source ZIP."),
        bullet("Generated outputs remain on the host through the Docker Compose outputs bind mount."),
        callout("Full model inference cannot run until the verified runtime TAR has been loaded under the expected Docker tag."),
        p("Repository-root entry points", "Subsection"),
        code(".\\Start.exe\n.\\robustness_experiments\\Start.ps1"),
        PageBreak(),
    ]

    items += [
        p("2  System requirements", "Section"),
        info_table([
            ("Operating system", "Windows 10 or Windows 11, 64-bit."),
            ("Container runtime", "Docker Desktop with Linux containers and the WSL 2 backend."),
            ("GPU", "NVIDIA GPU exposed to Docker. GPU access is required for full inference."),
            ("Driver", "NVIDIA driver compatible with the CUDA 12.8 runtime in the supplied image."),
            ("Shell", "Windows PowerShell 5.1 or PowerShell 7."),
            ("Network", "Required to download the OneDrive archive and while the project build installs Graphviz."),
            ("Host Graphviz", "Required only for host-side PDG Atlas rendering tests; the project Docker image installs it automatically."),
            ("Storage", "Allow space for the 4.439 GiB TAR, extracted Docker layers, project image, and generated outputs."),
        ]),
        p("Verify Docker Desktop", "Subsection"),
        code("docker version\ndocker info"),
        p("Verify host and container GPU access", "Subsection"),
        code("nvidia-smi\ndocker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi"),
        callout("If the host GPU works but the container command fails, update Docker Desktop and the NVIDIA driver, then restart Windows."),
        PageBreak(),
    ]

    download_link = f'<link href="{ONEDRIVE_URL}" color="#2563EB"><u>Open the verified UNSW OneDrive Docker delivery folder</u></link>'
    items += [
        p("3  Download and load the verified runtime", "Section"),
        p(download_link),
        p("Required archive", "Subsection"),
        info_table([
            ("Filename", ARCHIVE),
            ("Size", "4,766,494,208 bytes (4.439 GiB)"),
            ("SHA-256", CHECKSUM),
            ("Docker tag", "deepwukong-rtx5060-cu128:experimental"),
            ("Image ID", "sha256:4735e489150a248ff4dc2040d366c5c09721263db9f6d8f7b116d39c0d035aea"),
            ("Platform", "linux/amd64"),
        ], left=38 * mm),
        p("Verify the download", "Subsection"),
        code(f"Get-FileHash .\\{ARCHIVE} -Algorithm SHA256"),
        callout(f"The calculated SHA-256 must be exactly {CHECKSUM}. Do not load the archive if it differs."),
        p("Load and inspect the image", "Subsection"),
        code(f"docker load -i .\\{ARCHIVE}\ndocker image inspect deepwukong-rtx5060-cu128:experimental"),
        p("A verified test import of this exact TAR restored the expected tag successfully.", "Small"),
        PageBreak(),
    ]

    items += [
        p("4  Build and start ALMOND", "Section"),
        p("Extract the source ZIP", "Subsection"),
        p("Extract the complete source submission to a writable local directory. Do not run it directly from inside a ZIP. Open PowerShell in the repository root, which contains README.md and Start.exe."),
        p("Confirm required files", "Subsection"),
        code("Test-Path .\\Start.exe\nTest-Path .\\robustness_experiments\\Start.ps1\nTest-Path .\\scripts\\docker\\compose.yaml\nTest-Path .\\baselines\\deepwukong\\models\\deepwukong\\deepwukong_cwe119_best.ckpt"),
        p("Build the project image", "Subsection"),
        code("docker compose -f scripts/docker/compose.yaml build almond"),
        p("The build creates t17a-almond:latest. The Dockerfile installs Graphviz automatically and excludes archived outputs and the large PDG Atlas page set from the build context."),
        p("Start the system", "Subsection"),
        code(".\\Start.exe\n\n# Equivalent PowerShell entry point\n.\\robustness_experiments\\Start.ps1"),
        callout("Start.exe builds when required, launches the interactive console, serves dashboards on port 8000, and preserves outputs on the host."),
        PageBreak(),
    ]

    items += [
        p("5  Test and inspect results", "Section"),
        p("Run the complete container test suite", "Subsection"),
        code("docker compose -f scripts/docker/compose.yaml run --rm almond tests"),
        callout("Verified result in the target Docker/GPU environment: Ran 66 tests - OK."),
        p("Verify GPU access through ALMOND", "Subsection"),
        code("docker run --rm --gpus all --entrypoint python `\n  t17a-almond:latest `\n  -c \"import torch; print(torch.cuda.is_available())\""),
        p("The output must be True. Use nvidia-smi on the host or in a CUDA container to inspect the detected GPU name."),
        p("Browser locations", "Subsection"),
        info_table([
            ("Dashboard index", "http://localhost:8000/outputs/index.html"),
            ("PDG Atlas", "http://localhost:8000/robustness_experiments/showcase/deepwukong_pdg_showcase.html"),
            ("Final run", "outputs/run_20260731_124703_code_all_input_sources/dashboard.html"),
            ("Graph comparison", "outputs/run_20260731_124703_code_all_input_sources/graph_comparison/dashboard.html"),
        ]),
        p("Use docker compose run rather than docker compose up for the interactive console because it requires direct terminal input.", "Small"),
        PageBreak(),
    ]

    items += [
        p("6  Troubleshooting and assessor checklist", "Section"),
        info_table([
            ("Docker daemon unavailable", "Start Docker Desktop, wait for the Linux engine to report Running, then repeat docker version."),
            ("Checksum mismatch", "Delete the incomplete download, download the TAR again from the documented OneDrive folder, and recheck SHA-256."),
            ("Base image not found", "Repeat docker load and confirm that docker image inspect shows the exact expected tag."),
            ("GPU unavailable", "Confirm nvidia-smi works on the host and in a CUDA container. Update Docker Desktop and the NVIDIA driver if required."),
            ("PowerShell blocked", "Run Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass. Do not change the machine-wide policy."),
            ("Graphviz tests fail", "For container tests, rebuild the project image. For host tests, install Graphviz and reopen the terminal."),
            ("Dashboard has no data", "Confirm outputs exists on the host and the final run contains dashboard.html and summary.json."),
        ], left=50 * mm),
        p("Assessor final checklist", "Subsection"),
        bullet("The OneDrive folder opens and the 4.439 GiB TAR downloads successfully."),
        bullet("The archive checksum and Docker tag match this manual."),
        bullet("Docker Desktop and the NVIDIA GPU are available."),
        bullet("The project image builds from the submitted source."),
        bullet("All 66 container tests pass."),
        bullet("Start.exe launches the console and the Dashboard, PDG Atlas, and graph comparison open."),
        callout("Retain the OneDrive link, archive checksum, test output, and final successful launch evidence with the submission."),
    ]
    return items


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=19 * mm,
        bottomMargin=21 * mm,
        title="ALMOND Installation Manual",
        author="T17A ALMOND",
        subject="Verified installation and Docker image delivery instructions",
    )
    document.build(story(), onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
