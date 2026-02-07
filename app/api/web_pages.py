"""
Web Pages Router.
Serves static pages like Privacy Policy and Terms of Service.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """Privacy Policy Page."""
    return """
    <html>
        <head>
            <title>Privacy Policy - Subhamasthu</title>
            <style>body { font-family: sans-serif; max_width: 800px; margin: 0 auto; padding: 20px; }</style>
        </head>
        <body>
            <h1>Privacy Policy</h1>
            <p><strong>Effective Date:</strong> February 8, 2026</p>
            <p>Subhamasthu ("we", "our", "us") respects your privacy. This Privacy Policy explains how we handle your personal information.</p>
            
            <h2>1. Information We Collect</h2>
            <p>We collect your phone number and name when you use our WhatsApp chatbot. We also collect transaction details when you make a donation.</p>
            
            <h2>2. How We Use Information</h2>
            <p>We use your information to:</p>
            <ul>
                <li>Facilitate the Sankalp and Pooja services.</li>
                <li>Send you updates, receipts, and photos of the service performed.</li>
                <li>Provide customer support.</li>
            </ul>
            
            <h2>3. Data Sharing</h2>
            <p>We do not sell your personal data. We share data only with:</p>
            <ul>
                <li><strong>Meta/WhatsApp:</strong> To send and receive messages.</li>
                <li><strong>Razorpay:</strong> To process donations securely.</li>
                <li><strong>Cloudinary:</strong> To store and serve media files.</li>
            </ul>
            
            <h2>4. Contact Us</h2>
            <p>If you have questions, please contact us at support@subhamasthu.com.</p>
        </body>
    </html>
    """

@router.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    """Terms of Service Page."""
    return """
    <html>
        <head>
            <title>Terms of Service - Subhamasthu</title>
            <style>body { font-family: sans-serif; max_width: 800px; margin: 0 auto; padding: 20px; }</style>
        </head>
        <body>
            <h1>Terms of Service</h1>
            <p><strong>Effective Date:</strong> February 8, 2026</p>
            
            <h2>1. Acceptance of Terms</h2>
            <p>By using the Subhamasthu WhatsApp chatbot, you agree to these Terms of Service.</p>
            
            <h2>2. Description of Service</h2>
            <p>Subhamasthu facilitates remote religious services (Pooja, Annadanam) at various temples in India on behalf of users.</p>
            
            <h2>3. Donations and Refunds</h2>
            <p>All donations are voluntary. Since funds are used for perishable goods (food for Annadanam) or service arrangements, refunds are generally not provided once the service is performed. Disputed transactions will be reviewed on a case-by-case basis.</p>
            
            <h2>4. Limitation of Liability</h2>
            <p>We strive to perform all services diligently but are not liable for delays caused by temple authorities or force majeure events.</p>
            
            <h2>5. Changes to Terms</h2>
            <p>We modify these terms at any time. Continued use of the service constitutes acceptance of modified terms.</p>
        </body>
    </html>
    """
@router.get("/data-deletion", response_class=HTMLResponse)
async def data_deletion():
    """Data Deletion Instructions Page."""
    return """
    <html>
        <head>
            <title>Data Deletion Instructions - Subhamasthu</title>
            <style>body { font-family: sans-serif; max_width: 800px; margin: 0 auto; padding: 20px; }</style>
        </head>
        <body>
            <h1>Data Deletion Instructions</h1>
            <p>Subhamasthu respects your privacy and right to be forgotten.</p>
            
            <h2>How to Request Data Deletion</h2>
            <p>If you wish to remove your data (phone number, name, and service history) from our records, please follow these steps:</p>
            
            <ol>
                <li>Send an email to <strong>support@subhamasthu.com</strong>.</li>
                <li>Subject Line: <strong>Data Deletion Request - [Your Phone Number]</strong>.</li>
                <li>In the body, confirm that you want your data deleted.</li>
            </ol>
            
            <p>We will process your request within 7 business days and confirm the deletion via email.</p>
        </body>
    </html>
    """
