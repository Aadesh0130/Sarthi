import logging
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("sarthi.sms")


class SMSService:
    @staticmethod
    def send_otp(phone: str, otp: str, expires_minutes: int = 5) -> bool:
        """
        Sends OTP message.
        If AUTH_DEV_MODE is enabled or credentials are not yet configured,
        securely prints the OTP exclusively to the backend server console.
        In production, securely dispatches SMS via Twilio API.
        """
        message_body = (
            f"Your Sārthi verification code is {otp}. "
            f"Valid for {expires_minutes} minutes. "
            f"Never share this code with anyone. - Sārthi Smart Tourism"
        )

        # Check for development mode or unconfigured provider
        has_twilio_creds = bool(
            settings.SMS_ACCOUNT_SID and
            settings.SMS_AUTH_TOKEN and
            settings.SMS_FROM_NUMBER
        )

        if settings.AUTH_DEV_MODE or not has_twilio_creds:
            # Print prominent developer console banner
            border = "=" * 64
            print("\n" + border)
            print("  [SARTHI AUTH - DEVELOPMENT MODE]")
            print("  SMS Provider Credentials Not Active or AUTH_DEV_MODE=true")
            print(f"  Target Phone : {phone}")
            print(f"  OTP Code     : >>> {otp} <<<")
            print(f"  Expires In   : {expires_minutes} minutes")
            print("  Security Notice: OTP is printed only to server stdout.")
            print("  It is NEVER exposed in the client API response.")
            print(border + "\n")
            return True

        # Production Twilio delivery
        try:
            from twilio.rest import Client

            client = Client(settings.SMS_ACCOUNT_SID, settings.SMS_AUTH_TOKEN)
            message = client.messages.create(
                body=message_body,
                from_=settings.SMS_FROM_NUMBER,
                to=phone
            )
            logger.info(f"SMS successfully dispatched to {phone}. SID: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch SMS via Twilio: {str(e)}")
            # Raise error in production so client knows delivery failed
            raise RuntimeError(f"Failed to send SMS to {phone}. Please try again later.")
