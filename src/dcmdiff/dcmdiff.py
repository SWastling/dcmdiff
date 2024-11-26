"""Find differences between DICOM instances, series or studies"""

import argparse
import difflib
import pathlib
import re
import sys
import webbrowser

import importlib.metadata
import pydicom

__version__ = importlib.metadata.version("dcmdiff")


# useful patterns for simplifying names
under = re.compile(r"[\s/^]")
underb = re.compile(r"^_+")
underrep = re.compile(r"_{2,}")
undere = re.compile(r"_+$")
remove = re.compile(r"[^A-Za-z0-9_-]")
removep = re.compile(r"[^A-Za-z0-9,.;:=%^&()_+-]")


def progress(count, total, message=None):
    """
    Print percentage progress to stdout during loop.

    :param count: Loop counter
    :type count: int
    :param total: Total number of iterations of loop
    :type total: str
    :param message: Optional message to accompany % progress
    :type message: str
    """
    if message is None:
        message = ""

    percents = round(100.0 * count / float(total), 1)

    if total == count:
        print("%s [%3d%%]" % (message, percents))
    else:
        print("%s [%3d%%]" % (message, percents), end="\r")


def simplify_under(name):
    """
    Turn spaces and carets into underscores, and tidy up repeated or leading/trailing underscores.

    :param name: string to be cleaned of spaces, carets and repeated underscores
    :type name: str
    :return: s - simplified name
    :rtype: str
    """
    s = under.subn("_", name)[0]
    s = underb.subn("", s)[0]
    s = undere.subn("", s)[0]
    s = underrep.subn("_", s)[0]
    s = remove.subn("", s)[0]

    return s


def simplify_series(desc):
    """
    Simplify series description.

    :param desc: series description
    :type desc: str
    :return: simplified series description
    :rtype: str
    """
    s = under.subn("_", desc)[0]
    s = remove.subn("", s)[0]
    return s


def read_tag_file(tag_fp):
    """
    Read text file containing a list of DICOM tags. Tags can be keywords
    e.g. RepetitionTime or combined group and element numbers e.g. 0x00180080"

    :param tag_fp: Text file containg a list of DICOM tags
    :type tag_fp: pathlib.Path
    :return: list of DICOM tags
    :rtype: list[pydicom.tag.Tag]
    """

    if tag_fp.is_file():
        f = open(tag_fp, "r")
        tc = f.read().splitlines()
    else:
        sys.stderr.write("ERROR: %s does not exist, exiting\n" % tag_fp)
        sys.exit(1)

    tc_list = []
    for element in tc:
        try:
            tag = pydicom.tag.Tag(element)
            tc_list.append(tag)
        except Exception as e:
            sys.stderr.write("WARNING: %s\n" % e)

    if len(tc_list) == 0:
        sys.stderr.write("ERROR: no tags found in %s, exiting\n" % tag_fp)
        sys.exit(1)
    else:
        return tc_list


def append_if_dicom(fp, ds_list):
    """
    Load DICOM dataset and append to a list if a given filepath is a file, DICOM
    and not a DICOMDIR

    :param fp: File to check and load
    :type fp: pathlib.Path
    :param ds_list: List of DICOM datasets
    :type ds_list: list[pydicom.dataset.Dataset]
    :return: List of DICOM datasets
    :rtype: list[pydicom.dataset.Dataset]
    """

    if fp.is_file() and pydicom.misc.is_dicom(fp):
        ds = pydicom.dcmread(fp, stop_before_pixels=True)

        sop_class = ds.file_meta.get("MediaStorageSOPClassUID", None)
        if sop_class != pydicom.uid.MediaStorageDirectoryStorage:
            ds_list.append(ds)

    return ds_list


def make_ds_list(pth):
    """
    Create a list of DICOM datasets

    :param pth: File or directory
    :type pth: pathlib.Path
    :return: List of DICOM datasets
    :rtype: list[pydicom.dataset.Dataset]
    """

    ds_list = []
    if pth.is_file():
        ds_list = append_if_dicom(pth, ds_list)

    elif pth.is_dir():
        pth_list_all = sorted(pth.rglob("*"))
        for pth_counter, pth_temp in enumerate(pth_list_all, 1):
            progress(
                pth_counter,
                len(pth_list_all),
                "** loading %d files" % (len(pth_list_all)),
            )
            ds_list = append_if_dicom(pth_temp, ds_list)

    else:
        sys.stderr.write("ERROR: %s is neither a file or directory\n" % pth)
        sys.exit(1)

    if len(ds_list) == 0:
        sys.stderr.write("ERROR: No valid DICOM files found, exiting\n")
        sys.exit(1)

    return ds_list


def sort_ds_list(ds_list):
    """
    Sort a list of DICOM datasets into a nested dictionary with the following
    levels/heirachy

    1.PATIENT with PatientID as the key
    2.STUDY with StudyInstanceUID as the key
    3.SERIES with SeriesInstanceUID as the key
    4.INSTANCE with SOPInstanceUID as the key

    :param ds_list: List of DICOM datasets
    :type ds_list: list[pydicom.dataset.Dataset]
    :return: Nested dictionary of DICOM datasets
    :rtype: dict

    """
    ds_dict = {}
    for ds_counter, ds in enumerate(ds_list, 1):
        progress(
            ds_counter,
            len(ds_list),
            "** sorting %d datasets" % (len(ds_list)),
        )

        if ds.PatientID not in ds_dict:
            pt_name = str(ds.get("PatientName", "unknown"))
            clean_pt_name = simplify_under(pt_name.lower())
            ds_dict[ds.PatientID] = {"patient_name": clean_pt_name}

        if ds.StudyInstanceUID not in ds_dict[ds.PatientID]:
            study_desc = str(ds.get("StudyDescription", "unknown"))
            study_date = str(ds.get("StudyDate", 20000101))
            study_time = str(ds.get("StudyTime", 120000.00)).split(".")[0]
            study_dts = study_date + "." + study_time
            clean_study_desc = simplify_series(study_desc)

            ds_dict[ds.PatientID][ds.StudyInstanceUID] = {
                "study_datetime": study_dts,
                "study_desc": clean_study_desc,
            }

        if ds.SeriesInstanceUID not in ds_dict[ds.PatientID][ds.StudyInstanceUID]:
            series_num = int(ds.get("SeriesNumber", 1))
            modality = str(ds.get("Modality", "unknown"))
            series_desc = str(ds.get("SeriesDescription", "unknown"))
            clean_series_desc = simplify_series(series_desc)
            ds_dict[ds.PatientID][ds.StudyInstanceUID][ds.SeriesInstanceUID] = {
                "series_num": series_num,
                "modality": modality,
                "series_desc": clean_series_desc,
            }

        if (
            ds.SOPInstanceUID
            not in ds_dict[ds.PatientID][ds.StudyInstanceUID][ds.SeriesInstanceUID]
        ):
            ds_dict[ds.PatientID][ds.StudyInstanceUID][ds.SeriesInstanceUID][
                ds.SOPInstanceUID
            ] = ds

    return ds_dict


def get_patient_ds_dict(ds_dict):
    """
    Get the nested dictionary of DICOM datasets belonging to a single patient
    i.e. with the following levels

    1.STUDY with StudyInstanceUID as the key
    2.SERIES with SeriesInstanceUID as the key
    3.INSTANCE with SOPInstanceUID as the key

    :param ds_dict: nested dictionary of DICOM datasets
    :type ds_dict: dict
    :return: Nested dictionary of DICOM datasets belonging to a patient
    :rtype: dict
    """

    patient_ids = list(ds_dict.keys())
    if len(patient_ids) == 1:
        patient_id = patient_ids[0]
        result = ds_dict[patient_id]
    else:
        print("** found %d patients:" % len(patient_ids))
        for counter, patient_id in enumerate(patient_ids):
            print(
                "%4d - %s-%s"
                % (counter, patient_id, ds_dict[patient_id]["patient_name"])
            )

        print("** select ONE patient:")
        pt_choice = int(input("? "))
        result = ds_dict[patient_ids[pt_choice]]

    return result


def get_study_ds_dict(ds_dict):
    """
    Get the nested dictionary of DICOM datasets belonging to a single study
    i.e. with the following levels

    1.SERIES with SeriesInstanceUID as the key
    2.INSTANCE with SOPInstanceUID as the key

    :param ds_dict: nested dictionary of DICOM datasets
    :type ds_dict: dict
    :return: Nested dictionary of DICOM datasets belonging to a patient
    :rtype: dict
    """

    study_uids = list(ds_dict.keys())
    # Remove the patient_name key from the list so that the only keys at the study
    # level are StudyInstanceUIDs
    study_uids.remove("patient_name")
    if len(study_uids) == 1:
        study_uid = study_uids[0]
        result = ds_dict[study_uid]
    else:
        print("*** found %d studies:" % len(study_uids))
        for counter, study_uid in enumerate(study_uids):
            print(
                "%4d - %s-%s"
                % (
                    counter,
                    ds_dict[study_uid]["study_datetime"],
                    ds_dict[study_uid]["study_desc"],
                )
            )

        print("*** select one study:")
        study_choice = int(input("? "))
        result = ds_dict[study_uids[study_choice]]

    return result


def get_all_series_details(pth):
    """
    Get the series information from a DICOM file or directory of DICOM files

    :param pth: File or directory
    :type pth: pathlib.Path
    :return: Series details (SeriesInstanceUID, SeriesNumber, Modality, SeriesDescription, Dictionary of Instances)
    :rtype: list [(str,int,str,str,dict)]
    """

    # Create a list of input files
    ds_list = make_ds_list(pth)

    # Sort all the DICOM files into a hierarchical dictionary
    ds_dict = sort_ds_list(ds_list)

    # Get the user to select one patient (if there are multiple)
    ds_pat_dict = get_patient_ds_dict(ds_dict)

    # Get the user to select one study (if there are multiple)
    ds_study_dict = get_study_ds_dict(ds_pat_dict)

    series_uids = list(ds_study_dict.keys())
    # Remove the study_datetime and study_desc keys from the list so that the
    # only keys are SeriesInstanceUIDs
    series_uids.remove("study_datetime")
    series_uids.remove("study_desc")
    series_details = []
    for series_uid in series_uids:
        series_num = ds_study_dict[series_uid]["series_num"]
        modality = ds_study_dict[series_uid]["modality"]
        series_desc = ds_study_dict[series_uid]["series_desc"]

        result = ds_study_dict[series_uid]
        series_details.append((series_uid, series_num, modality, series_desc, result))

    return series_details


def choose_series(all_ser_list):
    """
    Chose one series from a list

    :param all_ser_list: list of series details (SeriesInstanceUID, SeriesNumber, Modality, SeriesDescription, Dictionary of Instances)
    :type all_ser_list: list[(str,int,str,str,dict)]
    :return: Series details (SeriesInstanceUID, SeriesNumber, Modality, SeriesDescription, Dictionary of Instances)
    :rtype: (str,int,str,str,dict)
    """

    for counter, ser in enumerate(all_ser_list):
        print(
            "%4d - %04d-%s-%s"
            % (
                counter,
                ser[1],
                ser[2],
                ser[3],
            )
        )

    print("select one series (n=none):")
    ser_choice = input("? ")
    if ser_choice == "n":
        return
    else:
        ser_choice = int(ser_choice)
        return all_ser_list[ser_choice][4]


def find_matching_series(ref_modality, ref_ser_desc, test_ser_all):
    """
    Find matching series based on Modality and SeriesDescription

    :param ref_modality: modality
    :type ref_modality: str
    :param ref_ser_desc: series description
    :type ref_ser_desc: str
    :param test_ser_all: list of series details (SeriesInstanceUID, SeriesNumber, Modality, SeriesDescription, Dictionary of Instances)
    :type test_ser_all: list[(str,int,str,str,dict)]
    :return: dictionary of DICOM instances in chosen series
    :rtype: dict
    """

    match_ser = []

    for t_ser in test_ser_all:
        if ref_modality == t_ser[2] and ref_ser_desc == t_ser[3]:
            match_ser.append(t_ser)

    if len(match_ser) == 0:
        print(
            "*** No series with matching Modality and Series Description found. Would you like to pick one?"
        )
        t_series_ds_dict = choose_series(test_ser_all)
    elif len(match_ser) == 1:
        t_series_ds_dict = match_ser[0][4]
    else:
        print(
            "*** %d series with matching Modality and Series Description found:"
            % len(match_ser)
        )

        t_series_ds_dict = choose_series(match_ser)

    return t_series_ds_dict


def choose_instance(all_inst_list):
    """
    Chose one instance from a list

    :param all_inst_list: list of DICOM datasets (instances)
    :type all_inst_list: list[pydicom.dataset.Dataset]
    :return: DICOM dataset
    :rtype: pydicom.dataset.Dataset
    """

    for counter, ds in enumerate(all_inst_list):
        inst_num = int(ds.get("InstanceNumber", 1))
        print(
            "%4d - instance number %04d"
            % (
                counter,
                inst_num,
            )
        )

    print("select one instance (n=none):")
    ser_choice = input("? ")
    if ser_choice == "n":
        return
    else:
        ser_choice = int(ser_choice)
        return all_inst_list[ser_choice]


def find_matching_instance(r_inst_num, test_uid_dict):
    """
    Find matching instances based on InstanceNumber

    :param r_inst_num: Instance Number
    :type r_inst_num: int
    :param test_uid_dict: dictionary of instances to find match in
    :type test_uid_dict: dict
    :return: DICOM dataset
    :rtype: pydicom.dataset.Dataset
    """

    match_inst = []
    all_inst = []
    t_uids = list(test_uid_dict.keys())
    t_uids.remove("series_num")
    t_uids.remove("modality")
    t_uids.remove("series_desc")
    for t_uid in t_uids:
        all_inst.append(test_uid_dict[t_uid])
        t_inst_num = test_uid_dict[t_uid].get("InstanceNumber", 1)
        if t_inst_num == r_inst_num:
            match_inst.append(test_uid_dict[t_uid])

    if len(match_inst) == 0:
        if len(t_uids) == 1:
            t_ds = test_uid_dict[t_uids[0]]
        else:
            t_ds = None
    elif len(match_inst) == 1:
        t_ds = match_inst[0]
    else:
        print(
            "\n*** %d Instances with matching Instance Number found:" % len(match_inst)
        )
        t_ds = choose_instance(match_inst)

    return t_ds


def keep_tags(ds, tags_to_keep):
    """
    Keep selected tags in DICOM dataset

    :param ds: DICOM dataset
    :type ds: pydicom.dataset.Dataset
    :param tags_to_keep: list of tags to keep
    :type tags_to_keep: list[pydicom.tag.BaseTag]
    :return: DICOM dataset with tags removed
    :rtype: pydicom.dataset.Dataset
    """

    def callback(ds_a, elem):
        if elem.tag not in tags_to_keep:
            del ds_a[elem.tag]

    ds.walk(callback)

    return ds


def remove_tags(ds, tags_to_rm):
    """
    Remove selected tags from DICOM dataset

    :param ds: DICOM dataset
    :type ds: pydicom.dataset.Dataset
    :param tags_to_rm: list of tags to remove
    :type tags_to_rm: list[pydicom.tag.BaseTag]
    :return: DICOM dataset with tags removed
    :rtype: pydicom.dataset.Dataset
    """

    def callback(ds_a, elem):
        if elem.tag in tags_to_rm:
            del ds_a[elem.tag]

    ds.walk(callback)

    return ds


def remove_vr_tags(ds, vrs_to_remove):
    """
    Remove tags with a given value representation (VR) from DICOM dataset

    :param ds: DICOM dataset
    :type ds: pydicom.dataset.Dataset
    :param vrs_to_remove: list of value representations (VR) of tags to remove
    :type vrs_to_remove: list[str]
    :return: DICOM dataset with tags removed
    :rtype: pydicom.dataset.Dataset
    """

    def callback(ds_a, elem):
        if elem.VR in vrs_to_remove:
            del ds_a[elem.tag]

    ds.walk(callback)
    return ds


def remove_group_tags(ds, groups_to_remove):
    """
    Remove tags in a given group from DICOM dataset

    :param ds: DICOM dataset
    :type ds: pydicom.dataset.Dataset
    :param groups_to_remove: group to remove as hex str e.g. 0x10
    :type groups_to_remove: list[str]
    :return: DICOM dataset with tags removed
    :rtype: pydicom.dataset.Dataset
    """
    group_rm = []
    for group in groups_to_remove:
        group_rm.append(int(group, 16))

    def callback(ds_a, elem):
        if elem.tag.group in group_rm:
            del ds_a[elem.tag]

    ds.walk(callback)
    return ds


def tags_to_list(ds):
    """
    Convert DICOM dataset to a list of strings each terminated by a newline

    :param ds: DICOM dataset
    :type ds: pydicom.dataset.Dataset
    :return: list of strings
    :rtype: list[str]
    """
    return str(ds).splitlines(keepends=True)


def main():

    parser = argparse.ArgumentParser(
        description="Find differences between DICOM instances, series or studies"
    )

    parser.add_argument(
        "r",
        help="reference DICOM file or directory",
        type=pathlib.Path,
        metavar="FILE or DIR",
    )

    parser.add_argument(
        "t",
        help="test DICOM file or directory",
        type=pathlib.Path,
        metavar="FILE or DIR",
    )

    parser.add_argument(
        "-o",
        default="./htmldiff",
        help="output directory to store results(default %(default)s)",
        metavar="DIR",
        type=pathlib.Path,
    )

    parser.add_argument(
        "-c",
        help="file containing list of DICOM tags to compare in the reference and "
        "test DICOM files. Tags can be keywords e.g. RepetitionTime or "
        "combined group and element numbers e.g. 0x00180080",
        metavar="FILE",
        type=pathlib.Path,
    )

    parser.add_argument(
        "-context",
        action="store_true",
        default=False,
        help="produce a context format diff (default: %(default)s, i.e. full files shown)",
    )

    parser.add_argument(
        "-l",
        "--lines",
        type=int,
        default=1,
        metavar="NUM",
        help="number of context lines (default: %(default)s)",
    )

    parser.add_argument(
        "--compare-one-inst",
        dest="compare_one_inst",
        help="only compare one instance per series",
        action="store_true",
    )

    parser.add_argument(
        "--ignore-private",
        dest="ignore_private",
        help="ignore all elements with an odd group number",
        action="store_true",
    )

    parser.add_argument(
        "--ignore-vr",
        dest="ignore_vr",
        help="list of value-representations to ignore (e.g. AS, AT,"
        " CS, DA, DS, DT, FL, FD, IS, LO, LT, OB, OD, OF, OW, PN, SH, SL,"
        " SQ, SS, ST, TM, UI, UL, UN, US or UT)",
        nargs="+",
        type=str,
        metavar="VR",
    )

    parser.add_argument(
        "--ignore-group",
        dest="ignore_group",
        help="list of groups to ignore (e.g. 0x0008 or 0x0010 etc...)",
        nargs="+",
        type=str,
        metavar="GROUP",
    )

    parser.add_argument(
        "--ignore-tag",
        dest="ignore_tag",
        help="list of tags to ignore. Tags can be keywords e.g. RepetitionTime "
        "or combined group and element numbers e.g. 0x00180080",
        nargs="+",
        type=str,
        metavar="TAG",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    if len(sys.argv) == 1:
        sys.argv.append("-h")

    args = parser.parse_args()

    out_dir = args.o.resolve()

    if not out_dir.is_dir():
        out_dir.mkdir(parents=True, exist_ok=True)

    if args.c:
        print("* loading", args.c)
        tags_to_compare = read_tag_file(args.c)
    else:
        tags_to_compare = None

    print("* processing reference DICOM(s)")
    r_series_details = get_all_series_details(args.r)

    print("* processing test DICOM(s)")
    t_series_details = get_all_series_details(args.t)

    fp_study_html = out_dir / "study_index.html"

    f_study_html = open(fp_study_html, "w")
    f_study_html.writelines(
        [
            "<!DOCTYPE html>\n",
            "<html>\n",
            "<body>\n",
            "<h1>DICOM Study</h1>\n",
            "<p>Select a reference series to view differences:</p>\n",
            '<ol type= "1">\n',
        ]
    )

    print("* comparing DICOM instance(s) in series:")
    for r_series in r_series_details:
        ref_series_str = "%04d-%s-%s" % (
            r_series[1],
            r_series[2],
            r_series[3],
        )

        print("** %s:" % ref_series_str)
        fp_series_html = out_dir / (ref_series_str + ".html")
        f_series_html = open(fp_series_html, "w")

        f_study_html.writelines(
            ['<li><a href="%s">%s</a></li>\n' % (str(fp_series_html), ref_series_str)]
        )

        r_series_ds_dict = r_series[4]

        t_series_ds_dict = find_matching_series(
            r_series[2], r_series[3], t_series_details
        )

        if t_series_ds_dict is not None:
            t_series_str = "%04d-%s-%s" % (
                t_series_ds_dict["series_num"],
                t_series_ds_dict["modality"],
                t_series_ds_dict["series_desc"],
            )
            f_series_html.writelines(
                [
                    "<!DOCTYPE html>\n",
                    "<html>\n",
                    "<body>\n",
                    "<h1>Reference series: %s</h1>\n" % ref_series_str,
                    "<h1>Test series: %s</h1>\n" % t_series_str,
                    "<p>Select an instance to view differences:</p>\n",
                    '<ol type= "1">\n',
                ]
            )

            r_uids = list(r_series_ds_dict.keys())
            # Remove the series_num, modality and series_desc keys so
            # that the only keys in the list are SOPInstanceUIDs
            r_uids.remove("series_num")
            r_uids.remove("modality")
            r_uids.remove("series_desc")
            for instance_cnt, r_uid in enumerate(r_uids, 1):
                progress(
                    instance_cnt,
                    len(r_uids),
                    "*** comparing %d instances" % (len(r_uids)),
                )

                r_ds = r_series_ds_dict[r_uid]
                r_inst_num = int(r_ds.get("InstanceNumber", 1))

                fp_instance_html = out_dir / (r_ds.SOPInstanceUID + ".html")
                f_series_html.writelines(
                    [
                        '<li><a href="%s">%s</a></li>\n'
                        % (str(fp_instance_html), r_ds.SOPInstanceUID)
                    ]
                )

                t_ds = find_matching_instance(r_inst_num, t_series_ds_dict)

                if t_ds is not None:

                    rep = []
                    for ds in [r_ds, t_ds]:
                        if args.ignore_private:
                            ds.remove_private_tags()

                        if args.ignore_vr is not None:
                            ds = remove_vr_tags(ds, args.ignore_vr)
                            ds.file_meta = remove_vr_tags(ds.file_meta, args.ignore_vr)

                        if args.ignore_group is not None:
                            ds = remove_group_tags(ds, args.ignore_group)
                            ds.file_meta = remove_group_tags(
                                ds.file_meta, args.ignore_group
                            )

                        if args.ignore_tag:
                            tag_to_rm_list = []
                            for tag_to_rm in args.ignore_tag:
                                tag_to_rm_list.append(pydicom.tag.Tag(tag_to_rm))

                            ds = remove_tags(ds, tag_to_rm_list)
                            ds.file_meta = remove_tags(ds.file_meta, tag_to_rm_list)

                        if tags_to_compare is not None:
                            ds = keep_tags(ds, tags_to_compare)
                            ds.file_meta = keep_tags(ds.file_meta, tags_to_compare)

                        rep.append(tags_to_list(ds))

                    diff = difflib.HtmlDiff().make_file(
                        rep[0],
                        rep[1],
                        fromdesc="Reference",
                        todesc="Test",
                        context=args.context,
                        numlines=args.lines,
                    )

                    with open(fp_instance_html, "w") as f:
                        f.writelines(diff)
                else:

                    f_instance_html = open(fp_instance_html, "w")
                    f_instance_html.writelines(
                        [
                            "<!DOCTYPE html>\n",
                            "<html>\n",
                            "<body>\n",
                            "<h1>Instance %s</h1>\n" % r_ds.SOPInstanceUID,
                            "<p>No instance from test series found or selected for comparison</p>\n",
                            "</body>\n",
                            "</html>",
                        ]
                    )
                    f_instance_html.close()

                if args.compare_one_inst:
                    break

        else:
            f_series_html.writelines(
                [
                    "<!DOCTYPE html>\n",
                    "<html>\n",
                    "<body>\n",
                    "<h1>Reference series: %s</h1>\n" % ref_series_str,
                    "<p>No series from test study selected for comparison</p>\n",
                ]
            )

        if t_series_ds_dict is not None:
            f_series_html.writelines(["</ol>\n"])

        f_series_html.writelines(["</body>\n", "</html>"])
        f_series_html.close()

    f_study_html.writelines(["</ol>\n", "</body>\n", "</html>"])
    f_study_html.close()
    webbrowser.open(str(fp_study_html))


if __name__ == "__main__":  # pragma: no cover
    main()
