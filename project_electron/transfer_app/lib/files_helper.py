from os import stat
from os.path import isfile, getmtime, getsize, splitext
from pwd import getpwuid
import re
import datetime
import tarfile


from django.conf import settings


def has_files_to_process():
    files_to_process = []

    with open(settings.UPLOAD_LOG_FILE) as f:
        lines_with_data = []
        for line in f.readlines():
            # lline = line.rstrip()
            patterns = [
                'Date:(?P<date>\d{4}\-\d{2}\-\d{2})',
                'Time:(?P<time>[\d\:\-\.]+)\s',
                'File:(?P<file_path>[a-zA-Z0-9\-\_\/\.]+)'
            ]

            get_uploads = re.search('.+'.join(patterns), line);
            if get_uploads:
                file_path = str(get_uploads.group('file_path'))

                extension = splitext_(file_path)

                tar_accepted_ext = ['tar.gz', '.tar']

                if extension[-1] in tar_accepted_ext:
                    print 'this is a tar file'

                    # HANDLE tar files
                    tar_passed = False
                    try:
                        if tarfile.is_tarfile(file_path):
                            tar_passed = True
                            
                            
                    except Exception as e:
                        print e
                    if not tar_passed:
                        print 'we have a problem:Tar'
                        continue
                    bag_it_name = tar_has_top_level_only(file_path)
                    if not bag_it_name:
                        print 'tar has more than one top level'
                        continue
                    file_type = 'TAR'

                else:
                    # DOES FILE CURRENTLY EXIST
                    if not isfile(file_path):
                        print get_uploads.group('file_path')
                        print 'we have problems'
                        continue
                    file_type = 'OTHER'

                file_modtime =  file_modified_time(file_path)
                file_size =     file_get_size(file_path)
                file_own =    file_owner(file_path)

                # GETTING ORGANIZATION
                get_org = re.search('\/(?P<organization>org\d+)\/',get_uploads.group('file_path'))
                if not get_org:
                    print 'throw message in log'
                    continue

                data = {
                    'date':                 get_uploads.group('date'),
                    'time':                 get_uploads.group('time'),
                    'file_path':            file_path,
                    'file_name':            file_path.split('/')[-1],
                    'file_type' :           file_type,
                    'org':                  get_org.group('organization'),

                    'file_modtime':         file_modtime,
                    'file_size':            file_size,
                    'upload_user' :         file_own,
                    'auto_fail' :           False,
                    'bag_it_name':          bag_it_name,
                }
                print data

                files_to_process.append(data)
            else:
                # report to logs
                go = 1
    return files_to_process if files_to_process else False

def file_owner(file_path):
    return getpwuid(stat(file_path).st_uid).pw_name

def file_modified_time(file_path):
    return datetime.datetime.fromtimestamp(getmtime(file_path))

def file_get_size(file_path):
    return getsize(file_path)

def splitext_(path):
    # https://stackoverflow.com/questions/37896386/how-to-get-file-extension-correctly
    if len(path.split('.')) > 2:
        return path.split('.')[0],'.'.join(path.split('.')[-2:])
    return splitext(path)

def tar_has_top_level_only(file_path):
    items = []
    with tarfile.open(file_path,'r:*') as tfile:
        items = tfile.getnames()
        if not tfile.getmembers()[0].isdir:
            return False
    if not items:
        return False
    # items 0 should be the first of every split
    top_dir = items[0]
    for item in items:
        if item.split('/')[0] != top_dir:
            return False
    return top_dir

def tar_extract_all(file_path):
    extracted = False
    try:
        tf = tarfile.open(file_path, 'r:*')
        tf.extractall('/data/tmp/')
        tf.close()
        extracted = True
    except Exception as e:
        print e

    return extracted
