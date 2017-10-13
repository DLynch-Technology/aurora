# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.views.generic import TemplateView

from django.shortcuts import render
from orgs.models import Archives
from orgs.authmixins import LoggedInMixinDefaults


class AppraiseView(TemplateView):
    template_name = "appraise/main.html"

    def get_context_data(self, **kwargs):
        context = super(TemplateView, self).get_context_data(**kwargs)

        # This should filter by transfer status too
        context['uploads'] = Archives.objects.filter(organization = self.request.user.organization).order_by('created_time')
        return context
