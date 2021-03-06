from datetime import date
from dateutil.relativedelta import relativedelta

from django.db.models.signals import m2m_changed, pre_delete, post_save
from django.dispatch import receiver

from bag_transfer.accession.models import Accession
from bag_transfer.lib.files_helper import chown_path_to_root
from bag_transfer.lib.RAC_CMD import delete_system_group
from bag_transfer.models import (
    Archives,
    User,
    BagInfoMetadata,
    Organization,
    DashboardMonthData,
    DashboardRecordTypeData,
)


@receiver(pre_delete, sender=Organization)
def delete_organization(sender, instance, **kwargs):
    """Clean up system resources when an organization is deleted."""
    chown_path_to_root(instance.org_machine_upload_paths()[0])
    delete_system_group(instance.machine_name)


@receiver(m2m_changed, sender=User.groups.through)
def set_is_staff(sender, instance, **kwargs):
    """Ensure `is_staff` attribute is correctly set when User instances are saved."""
    instance.is_staff = (
        True
        if (
            any(
                name
                in [
                    "managing_archivists",
                    "accessioning_archivists",
                    "appraisal_archivists",
                ]
                for name in instance.groups.values_list("name", flat=True)
            )
            or (instance.is_superuser)
        )
        else False
    )
    instance.save()


@receiver(post_save, sender=Archives)
@receiver(pre_delete, sender=Archives)
def dashboard_data(sender, instance, **kwargs):
    """
    Updates dashboard data each time a transfer is saved or deleted, which
    avoids expensive data operations on the database.
    """
    today = date.today()
    current = today - relativedelta(years=1)
    if instance.process_status >= sender.TRANSFER_COMPLETED:
        while current <= today:
            for organization in Organization.objects.all():
                data = DashboardMonthData.objects.get_or_create(
                    month_label=current.strftime("%B"),
                    sort_date=int(str(current.year) + str(current.month)),
                    year=current.year,
                    organization=organization,
                )[0]
                data.upload_count = Archives.objects.filter(
                    organization=organization,
                    machine_file_upload_time__year=current.year,
                    machine_file_upload_time__month=current.month,
                ).count()
                data.upload_size = (
                    sum(
                        map(
                            int,
                            Archives.objects.filter(
                                organization=organization,
                                machine_file_upload_time__year=current.year,
                                machine_file_upload_time__month=current.month,
                            ).values_list("machine_file_size", flat=True),
                        )
                    )
                    / 1000000000
                )
                data.save()
            current += relativedelta(months=1)
    if instance.process_status >= sender.VALIDATED:
        for organization in Organization.objects.all():
            for label in set(
                BagInfoMetadata.objects.all().values_list("record_type", flat=True)
            ):
                data = DashboardRecordTypeData.objects.get_or_create(
                    organization=organization, label=label
                )[0]
                data.count = Archives.objects.filter(
                    organization=organization, metadata__record_type=label
                ).count()
                data.save()


@receiver(post_save, sender=Archives)
def update_accession_status(sender, instance, **kwargs):
    """
    Updates Accession status to COMPLETE if all of the transfers in an accession
    have finished processing.
    """
    if instance.process_status == Archives.ACCESSIONING_COMPLETE:
        accession = instance.accession
        last_update = sorted(
            set([t.process_status for t in accession.accession_transfers.all()])
        )[0]
        if last_update == Archives.ACCESSIONING_COMPLETE:
            accession.process_status = Accession.COMPLETE
            accession.save()
