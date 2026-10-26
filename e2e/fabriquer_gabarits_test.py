"""
Gabarits de TEST réalistes (bordures, titres, lignes d'écriture) pour
`parcours-gabarits.mjs`, plus deux fichiers à refuser.

    python e2e/fabriquer_gabarits_test.py /tmp/gabarits && E2E_TEMPLATE_DIR=/tmp/gabarits node e2e/parcours-gabarits.mjs
"""
import io
import sys

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

out = sys.argv[1]

# 1. Diplôme PDF vectoriel, A4 paysage, fond crème, double bordure dorée.
w, h = landscape(A4)
pdf = canvas.Canvas(f"{out}/diplome_test_vectoriel.pdf", pagesize=(w, h))
pdf.setFillColorRGB(0.98, 0.95, 0.88)
pdf.rect(0, 0, w, h, stroke=0, fill=1)
pdf.setStrokeColorRGB(0.69, 0.54, 0.18)
pdf.setLineWidth(8)
pdf.rect(18, 18, w - 36, h - 36)
pdf.setLineWidth(1.5)
pdf.rect(30, 30, w - 60, h - 60)
pdf.setFillColorRGB(0.12, 0.23, 0.43)
pdf.setFont("Times-Bold", 40)
pdf.drawCentredString(w / 2, h - 110, "DIPLÔME")
pdf.setFont("Times-Italic", 15)
pdf.drawCentredString(w / 2, h - 140, "MODÈLE DE TEST — décerné à")
pdf.setStrokeColorRGB(0.4, 0.4, 0.4)
pdf.setLineWidth(0.8)
pdf.line(150, h - 250, w - 150, h - 250)       # ligne du nom
pdf.setFont("Times-Roman", 12)
pdf.drawString(90, 95, "Signature du directeur")
pdf.line(80, 110, 260, 110)
pdf.drawString(w - 250, 95, "Date de délivrance")
pdf.line(w - 260, 110, w - 80, 110)
pdf.save()

# 2. Certificat PNG A4 portrait 300 dpi (2480 × 3508), bandeau vert.
img = Image.new("RGB", (2480, 3508), (250, 250, 246))
d = ImageDraw.Draw(img)
d.rectangle([60, 60, 2420, 3448], outline=(30, 110, 70), width=24)
d.rectangle([60, 60, 2420, 420], fill=(30, 110, 70))
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf", 150)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf", 70)
except OSError:
    font = small = ImageFont.load_default()
d.text((1240, 240), "CERTIFICAT DE SCOLARITÉ", fill=(255, 255, 255), font=font, anchor="mm")
d.text((1240, 560), "MODÈLE DE TEST", fill=(90, 90, 90), font=small, anchor="mm")
for y in (1500, 1900, 2250):
    d.line([(300, y), (2180, y)], fill=(160, 160, 160), width=4)
img.save(f"{out}/certificat_test_portrait.png", "PNG", dpi=(300, 300))

# 3. Fichiers à refuser.
with open(f"{out}/faux_png.png", "wb") as handle:
    handle.write(open(f"{out}/diplome_test_vectoriel.pdf", "rb").read())
with open(f"{out}/corrompu.pdf", "wb") as handle:
    handle.write(b"%PDF-1.7\n" + b"\x00 donnees tronquees " * 200)
print("ok")
