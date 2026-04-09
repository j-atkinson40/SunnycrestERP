"""Social Service Certificate PDF generator using WeasyPrint.

Produces a clean, professional letter-size PDF suitable as a
government-facing delivery confirmation document.
"""

from datetime import datetime
from decimal import Decimal


def generate_social_service_certificate_pdf(
    certificate_number: str,
    deceased_name: str,
    funeral_home_name: str,
    cemetery_name: str,
    product_name: str,
    product_price: Decimal,
    delivered_at: datetime,
    company_config: dict,
) -> bytes:
    """Render the certificate as a PDF and return raw bytes.

    Args:
        certificate_number: e.g. "SO-2025-0142-SSC"
        deceased_name: Full name of the deceased
        funeral_home_name: Resolved funeral home display name
        cemetery_name: Resolved cemetery display name
        product_name: Line-item description (e.g. "Social Service Graveliner")
        product_price: Unit price from the order line
        delivered_at: Timestamp when the delivery was completed
        company_config: Dict with keys: name, address_street, address_city,
                        address_state, address_zip, phone, email,
                        company_legal_name (optional)

    Returns:
        PDF file contents as bytes.
    """
    company_name = company_config.get("company_legal_name") or company_config.get("name", "")
    street = company_config.get("address_street", "")
    city = company_config.get("address_city", "")
    state = company_config.get("address_state", "")
    zipcode = company_config.get("address_zip", "")
    phone = company_config.get("phone", "")
    email = company_config.get("email", "")

    city_state_zip = ", ".join(filter(None, [city, state])) + (f" {zipcode}" if zipcode else "")

    date_issued = delivered_at.strftime("%B %d, %Y")  # January 14, 2025
    time_of_service = delivered_at.strftime("%-I:%M %p")  # 9:30 AM
    price_fmt = f"${product_price:,.2f}"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: letter portrait;
    margin: 1in 1in 1in 1in;
  }}
  body {{
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    color: #1a1a1a;
    line-height: 1.5;
    margin: 0;
    padding: 0;
  }}
  .header {{
    text-align: center;
    padding-bottom: 18px;
    border-bottom: 2px solid #1a1a1a;
    margin-bottom: 24px;
  }}
  .header .company-name {{
    font-size: 16pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
  }}
  .header .company-address {{
    font-size: 9pt;
    color: #555;
  }}
  .title {{
    text-align: center;
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 16px 0;
    border-top: 1.5px solid #333;
    border-bottom: 1.5px solid #333;
    margin-bottom: 24px;
  }}
  .meta-row {{
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
  }}
  .meta-label {{
    font-weight: 600;
    color: #333;
    width: 180px;
    flex-shrink: 0;
  }}
  .meta-value {{
    flex: 1;
    text-align: left;
  }}
  .section-title {{
    font-size: 11pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 10px 0 6px;
    border-top: 1.5px solid #333;
    border-bottom: 1.5px solid #333;
    margin: 20px 0 14px;
  }}
  .details-table {{
    width: 100%;
    border-collapse: collapse;
  }}
  .details-table tr td {{
    padding: 6px 0;
    vertical-align: top;
  }}
  .details-table tr td:first-child {{
    font-weight: 600;
    color: #333;
    width: 180px;
  }}
  .disclaimer {{
    margin-top: 30px;
    padding: 16px;
    border: 1px solid #ccc;
    background: #fafafa;
    font-size: 9.5pt;
    line-height: 1.6;
    color: #444;
  }}
  .footer {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 8pt;
    color: #888;
    padding: 12px 0;
    border-top: 1px solid #ddd;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="company-name">{_esc(company_name)}</div>
  <div class="company-address">
    {_esc(street)}<br>
    {_esc(city_state_zip)}<br>
    {_esc(phone)}{(' &middot; ' + _esc(email)) if email else ''}
  </div>
</div>

<div class="title">Service Delivery Certificate</div>

<table class="details-table">
  <tr>
    <td>Certificate No:</td>
    <td>{_esc(certificate_number)}</td>
  </tr>
  <tr>
    <td>Date Issued:</td>
    <td>{_esc(date_issued)}</td>
  </tr>
</table>

<div class="section-title">Service Details</div>

<table class="details-table">
  <tr>
    <td>Product:</td>
    <td>{_esc(product_name)}</td>
  </tr>
  <tr>
    <td>Price:</td>
    <td>{_esc(price_fmt)}</td>
  </tr>
  <tr>
    <td>Deceased:</td>
    <td>{_esc(deceased_name)}</td>
  </tr>
  <tr>
    <td>Funeral Home:</td>
    <td>{_esc(funeral_home_name)}</td>
  </tr>
  <tr>
    <td>Cemetery:</td>
    <td>{_esc(cemetery_name)}</td>
  </tr>
  <tr>
    <td>Date of Service:</td>
    <td>{_esc(date_issued)}</td>
  </tr>
  <tr>
    <td>Time of Service:</td>
    <td>{_esc(time_of_service)}</td>
  </tr>
</table>

<div class="disclaimer">
  This certificate confirms delivery of the above burial vault product
  for the purposes of government benefit program verification.<br><br>
  This document is not an invoice. The funeral home will receive a
  separate invoice through standard billing channels.
</div>

<div class="footer">
  {_esc(company_name)} &middot; {_esc(street)}, {_esc(city_state_zip)} &middot; {_esc(phone)}{(' &middot; ' + _esc(email)) if email else ''}
</div>

</body>
</html>"""

    from weasyprint import HTML  # type: ignore
    return HTML(string=html).write_pdf()


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
