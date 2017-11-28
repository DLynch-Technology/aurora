# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.utils.translation import gettext as _
from django.contrib.auth.models import AbstractUser
from django.db import models
from transfer_app import RAC_CMD
from django.urls import reverse

from django.contrib import messages
from django.conf import settings

from transfer_app.lib.ldap_auth import LDAP_Manager

class Organization(models.Model):
    is_active =     models.BooleanField(default=True)
    name =          models.CharField(max_length=60, unique=True)
    machine_name =  models.CharField(max_length=30, unique=True, default="orgXXX will be created here")
    created_time =  models.DateTimeField(auto_now = True)
    modified_time = models.DateTimeField(auto_now_add = True)

    def org_users(self):
        return User.objects.filter(organization=self).order_by('username')
    def active_users(self):
        return User.objects.filter(organization=self,is_active=True)
    def inactive_users(self):
        return User.objects.filter(organization=self,is_active=False)

    def org_root_dir(self):
        return "%s%s".format(settings.ORG_ROOT_DIR,self.machine_name)

    def save(self, *args, **kwargs):

        if self.pk is None:                         # Initial Save / Sync table
            results = RAC_CMD.add_org(self.name)
            if results[0]:
                self.machine_name = results[1]
            else:
                go = 1
                # and when it fails
        else:

            # SET USERS INACTIVE WHEN ORG IS SET TO INACTIVE
            orig = Organization.objects.get(pk=self.pk)
            if orig.is_active != self.is_active and not self.is_active:
                # what if ORG is RAC
                for u in self.org_users():
                    if u.is_active:
                        u.is_active = False
                        u.save()
                        print 'USER {} set to inactive!'.format(u.username)

        super(Organization,self).save(*args,**kwargs)

    @staticmethod
    def users_by_org():
        orgs = Organization.objects.all().order_by('name')
        if not orgs: return False
        data = []

        for org in orgs:
            data.append({
                'org' : org,
                'users': org.org_users()
            })
        return data

    @staticmethod
    def is_org_active(org):

        ## DOES ORG EXIST
        organization = {}
        try:
            organization = Organization.objects.get(machine_name=org)
        except Organization.DoesNotExist as e:
            print e
        if not organization:
            print 'org doesnt exist log and continue to next file'
            return False

        ## ORG ACTIVE
        if not organization.is_active:
            print 'org not acitve, log and continue'
            return False
        return organization

    def build_transfer_timeline_list(self):
        arc_by_date = {}
        org_arcs =  Archives.objects.filter(process_status__gte=20, organization=self).order_by('-created_time')
        for arc in org_arcs:
            if arc.created_time.date() not in arc_by_date:

                arc_by_date[arc.created_time.date()] = []
            arc_by_date[arc.created_time.date()].append(arc)
        return arc_by_date

    def __unicode__(self): return self.name
    def get_absolute_url(self):
        return reverse('orgs-edit', kwargs={'pk': self.pk})

    class Meta:
        ordering = ['name']

class User(AbstractUser):

    organization =          models.ForeignKey(Organization, null=True, blank=False)
    is_machine_account =    models.BooleanField(default=True)
    from_ldap =             models.BooleanField(editable=False, default=False)
    is_new_account =        models.BooleanField(default=False)
    is_org_admin =          models.BooleanField(default=False)

    AbstractUser._meta.get_field('email').blank = False

    def in_group(self,GRP):
        return User.objects.filter(pk=self.pk, groups_name=GRP).exists()

    def save(self, *args, **kwargs):

        if self.pk is None:

            pass
        else:

            if self.from_ldap:
                orig = User.objects.get(pk=self.pk)
                if orig.organization != self.organization:
                    if RAC_CMD.del_from_org(self.username):
                        if RAC_CMD.add2grp(self.organization.machine_name,self.username):
                                print 'GROUP CHANGED'

                    ## SHOULD ACTUALLY REMOVE ANY GROUPS THAT MATCH REGEX ORGXXX
                    if orig.organization:
                        pass
                        # remove from ORG
                        # if RAC_CMD.del_from_org(self.username,orig.organization.machine_name):

                        #     if RAC_CMD.add2grp(self.organization.machine_name,self.username):
                        #         print 'GROUP CHANGED'
                    else:
                        if RAC_CMD.add2grp(self.organization.machine_name,self.username):
                            print 'GROUP CHANGED'

                        # FIRST TIME an ORG is added this will set account to not new
                        if self.is_new_account:
                            self.is_new_account = False

        if self.username[:2] == "va":
            if not self.is_staff:
                self.is_staff = True
                print 'SET to RAC USER!'


        super(User,self).save(*args,**kwargs)

    def total_uploads(self):
        return Archives.objects.filter(process_status__gte=20, user_uploaded=self).count()

    @staticmethod
    def refresh_ldap_accounts():
        ldap_man = LDAP_Manager()

        new_accounts = 0

        if ldap_man.get_all_users():

            ldapusers = [u.lower() for u in User.objects.filter(from_ldap=True).values_list('username',flat=True)]


            for uid in ldap_man.users:
                uid = uid.strip().lower()
                if uid not in ldapusers:
                    # CREATE USER ACCOUNT ON SERVER
                    if RAC_CMD.add_user(uid):

                        new_user = User.objects.create_user(uid,None,None)
                        new_user.is_active = False
                        new_user.from_ldap = True
                        new_user.is_new_account = True


                        ## should AUTO SET TO RAC
                        if uid[:2] == "va":
                            primary_org = Organization.objects.all().order_by('pk')
                            if primary_org:
                                new_user.organization = primary_org[0]
                                print 'USER AUTO ADDED TO PRIMARY ORG'


                        new_user.save()
                        new_accounts += 1
        return new_accounts


    @staticmethod
    def is_user_active(u,org):
        user = {}
        try:
            print 'i am here'
            user = User.objects.get(username = u, organization =org)
        except User.DoesNotExist as e:
            print e
        if not user:
            print 'not a user or not in org'
            return False
        if not user.is_active:
            print 'this would help to chain different message'
            return False
        return user

    def get_absolute_url(self):
        return reverse('users-detail', kwargs={'pk': self.pk})

    class Meta:
        ordering = ['username']

class Archives(models.Model):
    machine_file_types = (
        ('ZIP', 'zip'),
        ('TAR', 'tar'),
        ('OTHER', 'OTHER')
    )
    processing_statuses = (
        (10, 'Transfer Started'),
        (20, 'Transfer Completed'),
        (30, 'Invalid'),
        (40, 'Validated'),
        (60, 'Rejected'),
        (70, 'Accepted'),
        (90, 'Accessioned')
    )

    organization =          models.ForeignKey(Organization)
    user_uploaded =         models.ForeignKey(User, null=True)
    machine_file_path =          models.CharField(max_length=100)
    machine_file_size =     models.CharField(max_length= 30)
    machine_file_upload_time = models.DateTimeField()
    machine_file_identifier = models.CharField(max_length=255,unique=True)
    machine_file_type =     models.CharField(max_length=5,choices=machine_file_types)
    bag_it_name =           models.CharField(max_length=60)
    bag_it_valid =          models.BooleanField(default=False)

    additional_error_info = models.CharField(max_length=255,null=True,blank=True)
    process_status =        models.PositiveSmallIntegerField(choices=processing_statuses,default=20)
    created_time =          models.DateTimeField(auto_now=True) # process time
    modified_time =         models.DateTimeField(auto_now_add=True)

    def bag_or_failed_name(self):
        return self.bag_it_name if self.bag_it_valid else self.machine_file_path.split('/')[-1]

    def gen_identifier(self,fname,org,date,time):
        return "{}{}{}{}".format(fname,org,date,time)

    def get_error_codes(self):
        if self.bag_it_valid:
            return ''
        return [b.code.code_desc for b in self.get_errors()]

    def get_errors(self):
        if self.bag_it_valid:
            return None
        return [b for b in BAGLog.objects.filter(archive=self).exclude(code__code_short__in=['ASAVE','PBAG'])]


    def get_bag_validations(self):
        if not self.bag_it_valid:
            return False
        items = BAGLog.objects.filter(archive=self,code__code_short__in=['PBAG','PBAGP'])
        if not items or len(items) < 2:
            return False
        data = {}
        for item in items:
            data[item.code.code_short] = item.created_time
        return data

      def get_bag_failure(self, LAST_ONLY = True):
        if self.bag_it_valid:
            return False
        flist = [
            'NORG','BFNM',
            'BTAR','BTAR2','BZIP','BZIP2',
            'BDIR','EXERR',
            'GBERR', 'RBERR', 
            'MDERR', 'DTERR', 'FSERR',
            'VIRUS',
        ]
        get_error_obj = BAGLog.objects.filter(archive=self,code__code_short__in=flist)
        if not get_error_obj:
            return False
        return get_error_obj[0] if LAST_ONLY else get_error_obj

    def get_additional_errors(self):
        errs = []
        codes = []
        failures = self.get_bag_failure(LAST_ONLY=False)
        for fails in failures:
            codes.append(fails.code.code_short)

        if 'BZIP2' in codes or 'BTAR2' in codes:
            errs.append('Transfer contained more than one top level directory')



        if self.additional_error_info:
            errs.append(self.additional_error_info)
        return errs

    def get_transfer_logs(self):
        return BAGLog.objects.filter(archive=self)

    def setup_save(self, obj):
        """Builds additional info where more info is required than ecode short"""

        if obj['auto_fail_code'] == 'VIRUS':
            # IF CONTAINS a VIRUS, BUILD additional info
            self.additional_error_info = 'Virus found in: {}'.format([k for k in obj['virus_scanresult']][0])
        elif obj['auto_fail_code'] == 'FSERR':
            self.additional_error_info = 'Bag size ({}) is larger then maximum allow size ({})'.format(obj['file_size'], (settings.TRANSFER_FILESIZE_MAX * 1000))

    class Meta:
        ordering = ['machine_file_upload_time']

class BAGLogCodes(models.Model):

    eCat_bagit_validation = ['BTAR2','BZIP2',]
    eCat_rac_profile = ['FSERR','MDERR','DTERR']

    code_short = models.CharField(max_length=5)
    code_types = (
        ('T', 'Transfer'),
        ('E', 'Error'),
        ('I', 'Info'),

    )
    code_type = models.CharField(max_length=5, choices=code_types)
    code_desc = models.CharField(max_length=60)
    def __unicode__(self):
        return "{} : {}".format(self.code_short,self.code_desc)

class BAGLog(models.Model):

    code = models.ForeignKey(BAGLogCodes)
    archive = models.ForeignKey(Archives, blank=True,null=True)
    log_info = models.CharField(max_length=255, null=True, blank=True)
    created_time = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        val = "-- : {}".format(self.code.code_desc)
        if self.archive:
            val = "{} : {}".format( self.archive.bag_or_failed_name(), self.code.code_desc)
        return val

    @classmethod
    def log_it(cls, code, archive = None):
        try:
            print code
            item = cls(
                code = BAGLogCodes.objects.get(code_short=code),
                archive = archive
            ).save()


            if archive:
                if code in BAGLogCodes.eCat_bagit_validation:
                    cls.log_it('GBERR',archive)

                if code in BAGLogCodes.eCat_rac_profile:
                    cls.log_it('RBERR',archive)

            return True
        except Exception as e:
            print e
        else:
            return False

    class Meta:
        ordering = ['-created_time']