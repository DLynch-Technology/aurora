from dateutil import tz
import json
import requests

from django.views.generic import DetailView, ListView, View
from django_datatables_view.base_datatable_view import BaseDatatableView
from django.db.models import CharField, F
from django.db.models.functions import Concat
from django.contrib import messages
from django.shortcuts import render, redirect, reverse

from aurora import settings
from bag_transfer.accession.models import Accession
from bag_transfer.accession.forms import AccessionForm, CreatorsFormSet
from bag_transfer.accession.db_functions import GroupConcat
from bag_transfer.api.serializers import AccessionSerializer
from bag_transfer.lib.clients import ArchivesSpaceClient
from bag_transfer.lib.view_helpers import file_size
from bag_transfer.mixins.formatmixins import JSONResponseMixin
from bag_transfer.mixins.authmixins import ArchivistMixin, AccessioningArchivistMixin
from bag_transfer.models import (
    Archives,
    RecordCreators,
    BAGLog,
    LanguageCode,
)
from bag_transfer.rights.models import RightsStatement


class AccessionView(ArchivistMixin, JSONResponseMixin, ListView):
    template_name = "accession/main.html"
    model = Accession

    def get(self, request, *args, **kwargs):
        if request.is_ajax():
            return self.handle_ajax_request(request)
        return render(
            request,
            self.template_name,
            {
                "uploads": Archives.objects.filter(process_status=Archives.ACCEPTED)
                .annotate(
                    transfer_group=Concat(
                        "organization",
                        "metadata__record_type",
                        GroupConcat("metadata__record_creators"),
                        output_field=CharField(),
                    )
                )
                .order_by("transfer_group"),
                "accessions": Accession.objects.all(),
                "meta_page_title": "Accessioning Queue",
                "deliver": True if settings.DELIVERY_URL else False,
            },
        )

    def handle_ajax_request(self, request):
        """Handles JavaScript AJAX requests."""
        rdata = {}
        rdata["success"] = 0
        if request.user.has_privs("ACCESSIONER"):
            if "accession_id" in request.GET:
                try:
                    accession = Accession.objects.get(pk=request.GET["accession_id"])
                    accession_data = AccessionSerializer(
                        accession, context={"request": request}
                    )
                    resp = requests.post(
                        settings.DELIVERY_URL,
                        data=json.dumps(
                            accession_data.data, indent=4, sort_keys=True, default=str
                        ),
                        headers={
                            "Content-Type": "application/json",
                            "apikey": settings.API_KEY,
                        },
                    )
                    resp.raise_for_status()
                    accession.process_status = Accession.DELIVERED
                    accession.save()
                    rdata["success"] = 1
                except Exception as e:
                    rdata["error"] = str(e)
        return self.render_to_json_response(rdata)


class AccessionDetailView(AccessioningArchivistMixin, DetailView):
    template_name = "accession/detail.html"
    model = Accession


class AccessionCreateView(AccessioningArchivistMixin, JSONResponseMixin, View):
    template_name = "accession/create.html"
    model = Accession
    form_class = AccessionForm

    def post(self, request, *args, **kwargs):
        """Saves accessions, and delivers data to DELIVERY_URL if configured."""
        form = self.form_class(request.POST)
        creators_formset = CreatorsFormSet(request.POST)
        id_list = list(map(int, request.GET.get("transfers").split(",")))
        transfers_list = Archives.objects.filter(pk__in=id_list)
        rights_statements = (
            RightsStatement.objects.filter(archive__in=id_list)
            .annotate(rights_group=F("rights_basis"))
            .order_by("rights_group")
        )
        if form.is_valid() and creators_formset.is_valid():
            form.process_status = Accession.CREATED
            accession = form.save()
            creators_formset.save()
            merged_rights_statements = RightsStatement.merge_rights(rights_statements)
            for statement in merged_rights_statements:
                statement.accession = accession
                statement.save()
            for transfer in transfers_list:
                BAGLog.log_it("BACC", transfer)
                transfer.process_status = Archives.ACCESSIONING_STARTED
                transfer.accession = accession
                transfer.save()
            messages.success(request, " Accession created successfully!")
            if settings.DELIVERY_URL:
                try:
                    accession_data = AccessionSerializer(
                        accession, context={"request": request}
                    )
                    resp = requests.post(
                        settings.DELIVERY_URL,
                        data=json.dumps(
                            accession_data.data, indent=4, sort_keys=True, default=str
                        ),
                        headers={
                            "Content-Type": "application/json",
                            "apikey": settings.API_KEY,
                        },
                    )
                    resp.raise_for_status()
                    accession.process_status = Accession.DELIVERED
                    accession.save()
                    messages.success(request, "Accession data delivered.")
                except Exception as e:
                    print(e)
                    messages.error(
                        request, "Error delivering accession data: {}".format(e)
                    )
            return redirect("accession:detail", accession.pk)
        messages.error(
            request,
            "There was a problem with your submission. Please correct the error(s) below and try again.",
        )
        return render(
            request,
            self.template_name,
            {
                "meta_page_title": "Create Accession Record",
                "form": form,
                "creators_formset": creators_formset,
                "rights_statements": rights_statements,
                "transfers": transfers_list,
            },
        )

    def get(self, request, *args, **kwargs):
        """Performs initial grouping of transfer data."""
        if request.is_ajax():
            return self.handle_ajax_request(request)
        else:
            id_list = list(map(int, request.GET.get("transfers").split(",")))
            transfers_list = Archives.objects.filter(pk__in=id_list)
            rights_statements = (
                RightsStatement.objects.filter(archive__in=id_list)
                .annotate(rights_group=F("rights_basis"))
                .order_by("rights_group")
            )
            # should this get the source_organization from bag_data instead? Need to coordinate with data in other views
            organization = transfers_list[0].organization
            notes = {"appraisal": []}
            dates = {"start": [], "end": []}
            creators_list = []
            descriptions_list = []
            languages_list = []
            extent_files = 0
            extent_size = 0
            for transfer in transfers_list:
                bag_data = transfer.get_bag_data()
                extent_size = extent_size + int(
                    bag_data.get("payload_oxum", "0.0").split(".")[0]
                )
                extent_files = extent_files + int(
                    bag_data.get("payload_oxum", "0.0").split(".")[1]
                )
                dates["start"].append(bag_data.get("date_start", ""))
                dates["end"].append(bag_data.get("date_end", ""))
                notes["appraisal"].append(bag_data.get("appraisal_note", ""))
                descriptions_list.append(
                    bag_data.get("internal_sender_description", "")
                )
                for language in bag_data.get("language", []):
                    languages_list.append(language)
                creators_list += transfer.get_records_creators()
            for statement in rights_statements:
                rights_info = statement.get_rights_info_object()
                rights_granted = statement.get_rights_granted_objects()
                if not statement.rights_basis.lower() in notes:
                    notes[statement.rights_basis.lower()] = []
                notes[statement.rights_basis.lower()].append(
                    next(
                        value
                        for key, value in rights_info.__dict__.items()
                        if "_note" in key.lower()
                    )
                )
                for grant in rights_granted:
                    notes[statement.rights_basis.lower()].append(
                        grant.rights_granted_note
                    )
            record_creators = list(set(creators_list))
            languages_list = list(set(languages_list))
            language = LanguageCode.objects.get_or_create(code="und")[0]
            if len(languages_list) == 1:
                LanguageCode.objects.get_or_create(code=languages_list[0])[0]
            if len(languages_list) > 1:
                language = LanguageCode.objects.get_or_create(code="mul")[0]
            title = "{} {}".format(organization, bag_data.get("record_type", ""))
            if len(record_creators) > 0:
                title = "{}, {} {}".format(
                    organization,
                    ", ".join([creator.name for creator in record_creators]),
                    bag_data.get("record_type", ""),
                )
            form = AccessionForm(
                initial={
                    "title": title,
                    "start_date": sorted(dates.get("start", []))[0],
                    "end_date": sorted(dates.get("end", []))[-1],
                    "description": " ".join(set(descriptions_list)),
                    "extent_files": extent_files,
                    "extent_size": extent_size,
                    "access_restrictions": " ".join(
                        set(
                            notes.get("other", [])
                            + notes.get("license", [])
                            + notes.get("statute", [])
                        )
                    ),
                    "use_restrictions": " ".join(set(notes.get("copyright", []))),
                    "acquisition_type": organization.acquisition_type,
                    "appraisal_note": " ".join(set(notes.get("appraisal", []))),
                    "organization": organization,
                    "language": language,
                    "creators": record_creators,
                }
            )
            creators_formset = CreatorsFormSet(
                queryset=RecordCreators.objects.filter(name__in=record_creators)
            )
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "creators_formset": creators_formset,
                    "meta_page_title": "Create Accession Record",
                    "transfers": transfers_list,
                    "rights_statements": rights_statements,
                },
            )

    def handle_ajax_request(self, request):
        """Handles JavaScript AJAX requests."""
        rdata = {}
        rdata["success"] = False
        if "resource_id" in request.GET:
            try:
                client = ArchivesSpaceClient(
                    settings.ASPACE["baseurl"],
                    settings.ASPACE["username"],
                    settings.ASPACE["password"],
                    settings.ASPACE["repo_id"],
                )
                resp = client.get_resource(request.GET.get("resource_id"))
                rdata["title"] = "{} ({})".format(resp["title"], resp["id_0"])
                rdata["uri"] = resp["uri"]
                rdata["success"] = True
            except Exception as e:
                rdata["error"] = str(e)
        return self.render_to_json_response(rdata)


class SavedAccessionsDatatableView(ArchivistMixin, BaseDatatableView):
    """Handles processing of requests for Accessions in datatable, making page
    load time more performant."""
    model = Accession
    columns = [
        "title",
        "created",
        "extent_files",
        "accession_transfers__machine_file_identifier",
        "extent_size",
    ]
    order_columns = [
        "title",
        "created",
        "extent_files",
        "accession_transfers__machine_file_identifier",
        "extent_size",
    ]
    max_display_length = 500

    def get_filter_method(self):
        return self.FILTER_ICONTAINS

    def title(self, accession):
        return (
            "{} ({})".format(accession.title, accession.accession_number)
            if accession.accession_number
            else accession.title
        )

    def transfers(self, accession):
        transfers = accession.accession_transfers.count()
        label = "transfer" if transfers == 1 else "transfers"
        return "{} {}".format(transfers, label)

    def button(self, accession):
        button = "Accession not delivered"
        if self.request.user.can_accession():
            button = (
                '<a href="#" class="btn btn-primary pull-right deliver">Deliver Accession</a>'
                if (accession.process_status < Accession.DELIVERED)
                else '<p class="pull-right" style="margin-right:.7em;">'
                + accession.get_process_status_display()
                + "</p>"
            )
        return button

    def prepare_results(self, qs):
        json_data = []
        for accession in qs:
            json_data.append(
                [
                    "<a href='{}'>{}</a.".format(
                        reverse("accession:detail", kwargs={"pk": accession.pk}),
                        self.title(accession),
                    ),
                    accession.created.astimezone(tz.tzlocal()).strftime(
                        "%b %e, %Y %I:%M %p"
                    ),
                    "{} files ({})".format(
                        accession.extent_files, file_size(int(accession.extent_size))
                    ),
                    self.transfers(accession),
                    self.button(accession),
                    accession.pk,
                ]
            )
        return json_data
