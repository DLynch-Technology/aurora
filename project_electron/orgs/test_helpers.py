# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from datetime import datetime
from os import path, chdir, makedirs, listdir, rename
import pwd
import random
import string
from django.contrib.auth.models import Group
from orgs.models import Archives, Organization, User, BAGLogCodes
from rights.models import *
from project_electron import config, settings
from transfer_app.lib import files_helper as FH
from transfer_app.lib.transfer_routine import TransferRoutine

# General variables and setup routines


# still used??
def setup_tmp_dir():
    if path.isdir(config.TESTING_TMP_DIR):
        FH.remove_file_or_dir(config.TESTING_TMP_DIR)
    else:
        makedirs(config.TESTING_TMP_DIR)


def remove_tmp_dir():
    FH.remove_file_or_dir(config.TESTING_TMP_DIR)


def create_test_baglog_code(code):
    baglog_code = BAGLogCodes(
        code_short=code,
        code_type='T',
        code_desc='Test code',
    )
    baglog_code.save()
    print "BAGLogCode {} created".format(baglog_code)


# Returns a random string of specified length
def random_string(length):
    return ''.join(random.choice(string.ascii_letters) for m in range(length))


# Feturns a random date in a given year
def random_date(year):
    try:
        return datetime.strptime('{} {}'.format(random.randint(1, 366), year), '%j %Y')
    # accounts for leap year values
    except ValueError:
        random_date(year)


####################################
# CREATE TEST OBJECTS
####################################

# Creates a RecordType object for each value in list provided.
# If no list is given, RecordTypes created from a default list
def create_test_record_types(record_types=None):
    objects = []
    if record_types is None:
        record_types = [
            "administrative records", "board materials",
            "communications and publications", "grant records",
            "annual reports"]
    for record_type in record_types:
        object = RecordType.objects.create(
            name=record_type
        )
        objects.append(object)
        print 'Test record type {record_type} created'.format(record_type=object.name)
    return objects


# Creates a Group for each value in a list of names.
# If no list is given, Groups are created from a default list
def create_test_groups(names=None):
    groups = []
    if names is None:
        names = ['appraisal_archivists', 'accessioning_archivists', 'managing_archivists']
    for name in names:
        group = Group(name=name)
        group.save()
        groups.append(group)
        print 'Test group {group} created'.format(group=group.name)
    return groups


# Review
def create_test_org():
    test_org = Organization.objects.get_or_create(
        name='Ford Foundation',
        machine_name='org1'
    )
    print 'Test organization {org} created'.format(org=test_org[0].name)
    return test_org[0]


# Creates test user given a username and organization.
# If no username is given, the default username supplied in settings is used.
# If no organization is given, an organization is randomly chosen.
def create_test_user(username=None, org=None):
    if username is None:
        username = settings.TEST_USER['USERNAME']
    if org is None:
        org = random.choice(Organization.objects.all())
    test_user = User(
        username=username,
        email='test@example.org',
        organization=org)
    test_user.save()
    print 'Test user {username} created'.format(username=username)
    return test_user


# Review (From RightsStatement tests)
def create_test_archives(orgs):
    bags_ref = ['valid_bag']
    bags = []

    for ref in bags_ref:
        create_target_bags(ref, settings.TEST_BAGS_DIR, orgs[0])
        tr = TransferRoutine()
        tr.setup_routine()
        tr.run_routine()
        for trans in tr.transfers:
            machine_file_identifier = Archives().gen_identifier(
                trans['file_name'],
                trans['org'],
                trans['date'],
                trans['time']
            )
            archive = Archives.initial_save(
                orgs[0],
                None,
                trans['file_path'],
                trans['file_size'],
                trans['file_modtime'],
                machine_file_identifier,
                trans['file_type'],
                trans['bag_it_name']
            )

            # updating the name since the bag info reflects ford
            archive.organization.name = 'Ford Foundation'
            archive.organization.save()

            bags.append(archive)

    return bags


# review (From RightsStatement tests)
def create_target_bags(target_str, test_bags_dir, org):
    target_bags = [b for b in listdir(test_bags_dir) if b.startswith(target_str)]

    # setting ownership of paths to root
    root_uid = pwd.getpwnam('root').pw_uid
    index = 0

    for bags in target_bags:
        FH.anon_extract_all(
            path.join(test_bags_dir,bags),
            org.org_machine_upload_paths()[0]
        )
        # rename extracted path -- add index suffix to prevent colision
        created_path = path.join(org.org_machine_upload_paths()[0], bags.split('.')[0])
        new_path = '{}{}'.format(created_path, index)
        rename(created_path, new_path)
        index += 1

        # chowning path to root
        FH.chown_path_to_root(new_path)


# Review
def get_bag_extensions(bag_names):
    extensions = ['.tar', '.tar.gz', '.zip']
    bag_list = []
    for name in bag_names:
        bag_list.append(name)
        for e in extensions:
            bag_list.append('{}{}'.format(name, e))
    return bag_list


# Creates a rights statement given a record type, organization and rights basis.
# If any one of these values are not given, random values are assigned.
def create_rights_statement(record_type=None, org=None, rights_basis=None):
    if record_type is None:
        record_type = random.choice(RecordType.objects.all())
    if org is None:
        org = random.choice(Organization.objects.all())
    if rights_basis is None:
        rights_basis = random.choices(['Copyright', 'Statute', 'License', 'Other'])
    rights_statement = RightsStatement(
        organization=org,
        rights_basis=rights_basis,
    )
    rights_statement.save()
    rights_statement.applies_to_type.add(record_type)


# Creates a rights info object given a rights statement
# If no rights statement is given, a random value is selected
def create_rights_info(rights_statement=None):
    if rights_statement is None:
        rights_statement = random.choice(RightsStatement.objects.all())
    if rights_statement.rights_basis == 'Statute':
        rights_info = RightsStatementStatute(
            statute_citation=random_string(50),
            statute_applicable_start_date=random_date(1960),
            statute_applicable_end_date=random_date(1990),
            statute_end_date_period=20,
            statute_note=random_string(40)
        )
    elif rights_statement.rights_basis == 'Other':
        rights_info = RightsStatementOther(
            other_rights_basis=random.choice(['Donor', 'Policy']),
            other_rights_applicable_start_date=random_date(1978),
            other_rights_end_date_period=20,
            other_rights_end_date_open=True,
            other_rights_note=random_string(50)
        )
    elif rights_statement.rights_basis == 'Copyright':
        rights_info = RightsStatementCopyright(
            copyright_status=random.choice(['copyrighted', 'public domain', 'unknown']),
            copyright_applicable_start_date=random_date(1950),
            copyright_end_date_period=40,
            copyright_note=random_string(70)
        )
    elif rights_statement.rights_basis == 'License':
        rights_info = RightsStatementLicense(
            license_applicable_start_date=random_date(1980),
            license_start_date_period=10,
            license_end_date_open=True,
            license_note=random_string(60)
        )
    rights_info.rights_statement = rights_statement
    rights_info.save()


# Creates one or more rights granted objects, based on the grant count.
# If no rights statement is given, a random value is selected
def create_rights_granted(rights_statement=None, granted_count=1):
    if rights_statement is None:
        rights_statement = random.choice(RightsStatement.objects.all())
    all_rights_granted = []
    for x in xrange(granted_count):
        rights_granted = RightsStatementRightsGranted(
            rights_statement=rights_statement,
            act=random.choice(['publish', 'disseminate','replicate', 'migrate', 'modify', 'use', 'delete']),
            start_date=random_date(1984),
            end_date_period=15,
            rights_granted_note=random_string(100),
            restriction=random.choice(['allow', 'disallow', 'conditional'])
            )
        rights_granted.save()
        all_rights_granted.append(rights_granted)
    return all_rights_granted
