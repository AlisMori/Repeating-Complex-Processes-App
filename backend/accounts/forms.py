from email.utils import make_msgid

from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader


class SafeMessageIdPasswordResetForm(PasswordResetForm):
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
