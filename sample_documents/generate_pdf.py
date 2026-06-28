import os

def create_sample_pdf(output_path):
    # This generates a simple, valid PDF file containing Q3 carrier performance report.
    # It constructs basic PDF catalog, page tree, and text streams manually.
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page\n"
        b"   /Parent 2 0 R\n"
        b"   /MediaBox [0 0 595 842]\n"
        b"   /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>\n"
        b"   /Contents 4 0 R >>\n"
        b"endobj\n"
        b"4 0 obj\n"
        b"<< /Length 380 >>\n"
        b"stream\n"
        b"BT\n"
        b"/F1 16 Tf\n"
        b"72 750 Td\n"
        b"(Nexus Retail Logistics: Q3 Carrier Performance Review) Tj\n"
        b"0 -30 Td\n"
        b"/F1 12 Tf\n"
        b"(Document Ref: LPR-Q3-2026) Tj\n"
        b"0 -30 Td\n"
        b"(This report reviews the performance and SLA compliance of SwiftCargo and FedEx Freight.) Tj\n"
        b"0 -20 Td\n"
        b"(1. Carrier On-Time Performance Summary:) Tj\n"
        b"0 -15 Td\n"
        b"(- SwiftCargo achieved an On-Time Delivery rate of 94.2% across 340 shipments.) Tj\n"
        b"0 -15 Td\n"
        b"(- FedEx Freight achieved an On-Time Delivery rate of 88.5% across 210 shipments.) Tj\n"
        b"0 -15 Td\n"
        b"(- BlueStreak Logistics recorded 98.1% on-time performance on regional routes.) Tj\n"
        b"0 -25 Td\n"
        b"(2. Weather Delays & Hub Congestion:) Tj\n"
        b"0 -15 Td\n"
        b"(Major weather delays occurred at the Chicago transit hub, affecting FedEx deliveries.) Tj\n"
        b"0 -15 Td\n"
        b"(Average transit delay due to weather was 3.4 days in September 2026.) Tj\n"
        b"0 -25 Td\n"
        b"(3. Action Items and Carrier Penalty Charges:) Tj\n"
        b"0 -15 Td\n"
        b"(Apply standard 2.5% daily PO value late penalty on all delayed FedEx Freight shipments.) Tj\n"
        b"ET\n"
        b"endstream\n"
        b"endobj\n"
        b"xref\n"
        b"0 5\n"
        b"0000000000 65535 f\n"
        b"0000000009 00000 n\n"
        b"0000000058 00000 n\n"
        b"0000000115 00000 n\n"
        b"0000000282 00000 n\n"
        b"trailer\n"
        b"<< /Size 5 /Root 1 0 R >>\n"
        b"startxref\n"
        b"713\n"
        b"%%EOF\n"
    )
    
    with open(output_path, "wb") as f:
        f.write(pdf_content)
    print(f"Sample PDF successfully created at: {output_path}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.join(current_dir, "q3_sla_review.pdf")
    create_sample_pdf(target_path)
