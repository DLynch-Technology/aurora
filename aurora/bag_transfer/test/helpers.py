from datetime import datetime
from os import path, listdir, rename, chown
import pwd
import random
import string
from django.contrib.auth.models import Group
from bag_transfer.models import (
    AcceptBagItVersion,
    AcceptSerialization,
    Archives,
    BagItProfile,
    BagItProfileBagInfo,
    BagItProfileBagInfoValues,
    BAGLogCodes,
    LanguageCode,
    ManifestsAllowed,
    ManifestsRequired,
    Organization,
    RecordCreators,
    TagFilesRequired,
    TagManifestsRequired,
    User,
)
from bag_transfer.test import setup as org_setup
from bag_transfer.rights.models import (
    RecordType,
    RightsStatement,
    RightsStatementCopyright,
    RightsStatementLicense,
    RightsStatementOther,
    RightsStatementStatute,
    RightsStatementRightsGranted,
)
from aurora import settings
from bag_transfer.lib import files_helper as FH
from bag_transfer.lib.transfer_routine import TransferRoutine

# General variables and setup routines

####################################
# Generic functions
####################################


def random_string(length):
    """Returns a random string of specified length."""
    return "".join(random.choice(string.ascii_letters) for m in range(length))


def random_date(year):
    """Returns a random date in a given year."""
    try:
        return datetime.strptime("{} {}".format(random.randint(1, 366), year), "%j %Y")
    # accounts for leap year values
    except ValueError:

        random_date(year)


def random_name(prefix, suffix):
    """Returns a random name."""
    return "{} {} {}".format(prefix, random.choice(string.ascii_letters), suffix)


####################################
# CREATE TEST OBJECTS
####################################

def create_test_record_types(record_types=None):
    """Creates a RecordType object for each value in list provided.
    If no list is given, RecordTypes are create for each item in a default list."""
    objects = []
    if record_types is None:
        record_types = [
            "administrative records",
            "board materials",
            "communications and publications",
            "grant records",
            "annual reports",
        ]
    for record_type in record_types:
        object = RecordType.objects.create(name=record_type)
        objects.append(object)
        print("Test record type {record_type} created".format(record_type=object.name))
    return objects


def create_test_groups(names=None):
    """Creates a Group for each value in a list of names.
    If no list is given, Groups are created for each item in a default list."""
    groups = []
    if names is None:
        names = [
            "appraisal_archivists",
            "accessioning_archivists",
            "managing_archivists",
        ]
    for name in names:
        if not Group.objects.filter(name=name).exists():
            group = Group(name=name)
            group.save()
            groups.append(group)
            print("Test group {group} created".format(group=group.name))
        else:
            print("Test group {group} already exists".format(group=name))
            group = Group.objects.get(name=name)
            groups.append(group)
    return groups


def create_test_orgs(org_count=1):
    """creates random orgs based on org_count"""
    if org_count < 1:
        return False

    generated_orgs = []
    while True:
        if len(generated_orgs) == org_count:
            break
        new_org_name = random_name(
            random.choice(org_setup.POTUS_NAMES),
            random.choice(org_setup.COMPANY_SUFFIX),
        )
        try:
            Organization.objects.get(name=new_org_name)
            continue
        except Organization.DoesNotExist:
            pass

        test_org = Organization(
            name=new_org_name, machine_name="org{}".format((len(generated_orgs) + 1))
        )
        test_org.save()
        generated_orgs.append(test_org)

        print(
            "Test organization {} -- {} created".format(
                test_org.name, test_org.machine_name
            )
        )

    return generated_orgs


def delete_test_orgs(orgs=[]):
    for org in orgs:
        org.delete()


def create_test_baglogcodes():
    baglogcodes = (
        ("ASAVE", "I"),
        ("PBAG", "S"),
        ("PBAGP", "S"),
        ("GBERR", "BE"),
        ("DTERR", "BE"),
        ("MDERR", "BE"),
        ("RBERR", "BE"),
        ("BIERR", "BE"),
    )
    code_objects = []
    for code in baglogcodes:
        if not BAGLogCodes.objects.filter(code_short=code[0]).exists():
            bag_log_code = BAGLogCodes(
                code_short=code[0], code_type=code[1], code_desc=random_string(50),
            )
            bag_log_code.save()
            code_objects.append(bag_log_code)
    return code_objects


def create_test_user(username=None, org=None):
    """Creates test user given a username and organization.
    If no username is given, the default username supplied in settings is used.
    If no organization is given, an organization is randomly chosen.
    """
    if username is None:
        username = settings.TEST_USER["USERNAME"]
    if org is None:
        org = random.choice(Organization.objects.all())
    test_user = User(
        username=username, email="{}@example.org".format(username), organization=org
    )
    test_user.save()
    print("Test user {username} created".format(username=username))
    return test_user


def create_test_archive(transfer, org):
    """Creates Archive objects by running bags through TransferRoutine."""
    machine_file_identifier = Archives().gen_identifier()
    archive = Archives.initial_save(
        org,
        None,
        transfer["file_path"],
        transfer["file_size"],
        transfer["file_modtime"],
        machine_file_identifier,
        transfer["file_type"],
        transfer["bag_it_name"],
    )

    # updating the name since the bag info reflects ford
    archive.organization.name = "Ford Foundation"
    archive.organization.save()

    return archive


def create_target_bags(target_str, test_bags_dir, org, username=None):
    """Creates target bags to be picked up by a TransferRoutine based on a string.
    # This allows processing of bags serialized in multiple formats at once."""
    moved_bags = []
    target_bags = [b for b in listdir(test_bags_dir) if b.startswith(target_str)]
    if len(target_bags) < 1:
        return False

    index = 0

    for bags in target_bags:
        FH.anon_extract_all(
            path.join(test_bags_dir, bags), org.org_machine_upload_paths()[0]
        )
        # Renames extracted path -- add index suffix to prevent collision
        created_path = path.join(org.org_machine_upload_paths()[0], bags.split(".")[0])
        new_path = "{}{}".format(created_path, index)
        rename(created_path, new_path)
        index += 1

        # chowning path
        uid = pwd.getpwnam(username).pw_uid if username else pwd.getpwnam("root").pw_uid
        chown(new_path, uid, -1)
        moved_bags.append(new_path)

    return moved_bags


def run_transfer_routine():
    tr = TransferRoutine()
    tr.setup_routine()
    tr.run_routine()
    return tr


def create_rights_statement(record_type=None, org=None, rights_basis=None):
    """Creates a rights statement given a record type, organization and rights basis.
    If any one of these values are not given, random values are assigned."""
    record_type = (
        record_type if record_type else random.choice(RecordType.objects.all())
    )
    if org is None:
        org = random.choice(Organization.objects.all())
    if rights_basis is None:
        rights_basis = random.choices(["Copyright", "Statute", "License", "Other"])
    rights_statement = RightsStatement(organization=org, rights_basis=rights_basis,)
    rights_statement.save()
    rights_statement.applies_to_type.add(record_type)


def create_rights_info(rights_statement=None):
    """Creates a rights info object given a rights statement
    If no rights statement is given, a random value is selected"""
    rights_statement = (
        rights_statement
        if rights_statement
        else random.choice(RightsStatement.objects.all())
    )
    if rights_statement.rights_basis == "Statute":
        rights_info = RightsStatementStatute(
            statute_citation=random_string(50),
            statute_applicable_start_date=random_date(1960),
            statute_applicable_end_date=random_date(1990),
            statute_end_date_period=20,
            statute_note=random_string(40),
        )
    elif rights_statement.rights_basis == "Other":
        rights_info = RightsStatementOther(
            other_rights_basis=random.choice(["Donor", "Policy"]),
            other_rights_applicable_start_date=random_date(1978),
            other_rights_end_date_period=20,
            other_rights_end_date_open=True,
            other_rights_note=random_string(50),
        )
    elif rights_statement.rights_basis == "Copyright":
        rights_info = RightsStatementCopyright(
            copyright_status=random.choice(["copyrighted", "public domain", "unknown"]),
            copyright_applicable_start_date=random_date(1950),
            copyright_end_date_period=40,
            copyright_note=random_string(70),
        )
    elif rights_statement.rights_basis == "License":
        rights_info = RightsStatementLicense(
            license_applicable_start_date=random_date(1980),
            license_start_date_period=10,
            license_end_date_open=True,
            license_note=random_string(60),
        )
    rights_info.rights_statement = rights_statement
    rights_info.save()


def create_rights_granted(rights_statement=None, granted_count=1):
    """Creates one or more rights granted objects, based on the grant count.
    If no rights statement is given, a random value is selected."""
    rights_statement = (
        rights_statement
        if rights_statement
        else random.choice(RightsStatement.objects.all())
    )
    all_rights_granted = []
    for x in range(granted_count):
        rights_granted = RightsStatementRightsGranted(
            rights_statement=rights_statement,
            act=random.choice(
                [
                    "publish",
                    "disseminate",
                    "replicate",
                    "migrate",
                    "modify",
                    "use",
                    "delete",
                ]
            ),
            start_date=random_date(1984),
            end_date_period=15,
            rights_granted_note=random_string(100),
            restriction=random.choice(["allow", "disallow", "conditional"]),
        )
        rights_granted.save()
        all_rights_granted.append(rights_granted)
    return all_rights_granted


def create_test_bagitprofile(applies_to_organization=None):
    applies_to_organization = (
        applies_to_organization
        if applies_to_organization
        else random.choice(Organization.objects.all())
    )
    profile = BagItProfile(
        applies_to_organization=applies_to_organization,
        source_organization=random.choice(Organization.objects.all()),
        external_description=random_string(150),
        version=1,
        contact_email="test@example.org",
        allow_fetch=random.choice([True, False]),
        serialization=random.choice(["forbidden", "required", "optional"]),
    )
    profile.save()
    return profile


def create_test_manifestsallowed(bagitprofile=None):
    bagitprofile = (
        bagitprofile if bagitprofile else random.choice(BagItProfile.objects.all())
    )
    manifests_required = ManifestsAllowed(
        bagit_profile=bagitprofile, name=random.choice(["sha256", "sha512"])
    )
    manifests_required.save()
    return manifests_required


def create_test_manifestsrequired(bagitprofile=None):
    bagitprofile = (
        bagitprofile if bagitprofile else random.choice(BagItProfile.objects.all())
    )
    manifests_required = ManifestsRequired(
        bagit_profile=bagitprofile, name=random.choice(["sha256", "sha512"])
    )
    manifests_required.save()
    return manifests_required


def create_test_acceptserialization(bagitprofile=None):
    bagitprofile = (
        bagitprofile if bagitprofile else random.choice(BagItProfile.objects.all())
    )
    accept_serialization = AcceptSerialization(
        bagit_profile=bagitprofile,
        name=random.choice(
            ["application/zip", "application/x-tar", "application/x-gzip"]
        ),
    )
    accept_serialization.save()
    return accept_serialization


def create_test_acceptbagitversion(bagitprofile=None):
    bagitprofile = (
        bagitprofile if bagitprofile else random.choice(BagItProfile.objects.all())
    )
    acceptbagitversion = AcceptBagItVersion(
        name=random.choice(["0.96", 0.97]), bagit_profile=bagitprofile
    )
    acceptbagitversion.save()
    return acceptbagitversion


def create_test_tagmanifestsrequired(bagitprofile=None):
    bagitprofile = (
        bagitprofile if bagitprofile else random.choice(BagItProfile.objects.all())
    )
    tagmanifestsrequired = TagManifestsRequired(
        name=random.choice(["sha256", "sha512"]), bagit_profile=bagitprofile
    )
    tagmanifestsrequired.save()
    return tagmanifestsrequired


def create_test_tagfilesrequired(bagitprofile=None):
    bagitprofile = (
        bagitprofile if bagitprofile else random.choice(BagItProfile.objects.all())
    )
    tagfilesrequired = TagFilesRequired(
        name=random_string(150), bagit_profile=bagitprofile
    )
    tagfilesrequired.save()
    return tagfilesrequired


def create_test_bagitprofilebaginfo(bagitprofile=None, field=None):
    bagitprofile = (
        bagitprofile if bagitprofile else random.choice(BagItProfile.objects.all())
    )
    if field is None:
        field = random.choice(org_setup.BAGINFO_FIELD_CHOICES)
    bag_info = BagItProfileBagInfo(
        bagit_profile=bagitprofile,
        field=field,
        required=random.choice([True, False]),
        repeatable=random.choice([True, False]),
    )
    bag_info.save()
    return bag_info


def create_test_bagitprofilebaginfovalues(baginfo=None):
    baginfo = baginfo if baginfo else random.choice(BagItProfileBagInfo.objects.all())
    values = []
    for i in range(random.randint(1, 5)):
        bag_info_value = BagItProfileBagInfoValues(
            bagit_profile_baginfo=baginfo, name=random_string(25)
        )
        bag_info_value.save()
        values.append(bag_info_value)
    return values


def create_test_record_creators(count=1):
    record_creators = []
    for n in range(count):
        record_creator = RecordCreators(name=random_string(50))
        record_creator.save()
        record_creators.append(record_creator)
    return record_creators


def create_test_languages(count=1):
    languages = []
    for n in range(count):
        language = LanguageCode(code=random_string(3))
        language.save()
        languages.append(language)
    return languages


def get_accession_data(creator=None):
    creator = creator if creator else create_test_record_creators()[0]
    language = create_test_languages()[0]
    accession_data = {
        "use_restrictions": random_string(100),
        "access_restrictions": random_string(100),
        "resource": "http://example.org",
        "description": random_string(150),
        "end_date": random_date(1990),
        "extent_size": "17275340",
        "acquisition_type": random.choice(["donation", "deposit", "gift"]),
        "title": random_string(255),
        "accession_number": "2018.184",
        "start_date": random_date(1960),
        "extent_files": "14",
        "appraisal_note": random_string(150),
        "language": language.id,
        "creators": [creator.id],
        "form-0-id": creator.id,
        "form-MIN_NUM_FORMS": 0,
        "form-0-name": creator.name,
        "form-TOTAL_FORMS": 1,
        "form-INITIAL_FORMS": 1,
        "form-MAX_NUM_FORMS": 1000,
        "form-0-type": "organization",
    }
    return accession_data
