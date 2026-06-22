from django.contrib import admin
from .models import CycleInstance, CycleTask, CycleActivity, TaskDependency

admin.site.register(CycleInstance)
admin.site.register(CycleTask)
admin.site.register(CycleActivity)
admin.site.register(TaskDependency)