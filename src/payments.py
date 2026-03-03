import qrcode
from io import BytesIO

def generate_upi_qr(upi_id, amount, tx_ref):
    """
    Constructs the UPI string and generates a QR code image.
    Returns the image binary data.
    """
    upi_url = f"upi://pay?pa={upi_id}&pn=TelegramBot&am={amount}&cu=INR&tn={tx_ref}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    bio = BytesIO()
    bio.name = 'upi_qr.png'
    img.save(bio, 'PNG')
    bio.seek(0)
    
    return bio
