from email.utils import make_msgid
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def format_password_reset_expiry(timeout_seconds):
    if timeout_seconds % 3600 == 0:
        hours = timeout_seconds // 3600
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit}"

    minutes = timeout_seconds // 60
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit}"


class SafeMessageIdPasswordResetForm(PasswordResetForm):
    def save(
        self,
        domain_override=None,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="registration/password_reset_email.txt",
        use_https=False,
        token_generator=default_token_generator,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        email = self.cleaned_data["email"]

        if domain_override:
            site_name = domain = domain_override
        else:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain

        for user in self.get_users(email):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            reset_path = f"/auth/password-reset/confirm/{uid}/{token}"
            context = {
                "email": email,
                "domain": domain,
                "site_name": site_name,
                "uid": uid,
                "user": user,
                "token": token,
                "protocol": "https" if use_https else "http",
                "reset_url": urljoin(
                    f"{settings.FRONTEND_URL.rstrip('/')}/",
                    reset_path.lstrip("/"),
                ),
                "password_reset_expiry_text": format_password_reset_expiry(
                    settings.PASSWORD_RESET_TIMEOUT
                ),
                **(extra_email_context or {}),
            }
            self.send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                user.email,
                html_email_template_name=html_email_template_name,
            )

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        message_id_domain = "localhost"
        if from_email and "@" in from_email:
            message_id_domain = from_email.split("@", 1)[1] or message_id_domain

        email_message = EmailMultiAlternatives(
            subject,
            body,
            from_email,
            [to_email],
            headers={"Message-ID": make_msgid(domain=message_id_domain)},
        )
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        email_message.send()
