from django.contrib import admin
from .models import (
    Template,
    UserTemplate,
    Tag,
    TemplateTask,
    TemplateActivity,
    TemplateTaskTag,
    TemplateActivityTag,
)

admin.site.register(Template)
admin.site.register(UserTemplate)
admin.site.register(Tag)
admin.site.register(TemplateTask)
admin.site.register(TemplateActivity)
admin.site.register(TemplateTaskTag)
admin.site.register(TemplateActivityTag)