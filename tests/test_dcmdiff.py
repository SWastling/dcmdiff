import builtins
import copy
import pathlib

import mock
import pydicom
import pytest
from pydicom.fileset import FileSet

import dcmdiff.dcmdiff as dcmdiff

THIS_DIR = pathlib.Path(__file__).resolve().parent
TEST_DATA_DIR = THIS_DIR / "test_data"


@pytest.mark.parametrize(
    "args, expected_output",
    [
        ([0, 10, "doing thing"], "doing thing [  0%]\r"),
        ([5, 10], " [ 50%]\r"),
        ([10, 10], " [100%]\n"),
    ],
)
def test_progress(capsys, args, expected_output):
    dcmdiff.progress(*args)
    captured = capsys.readouterr()
    assert captured.out == expected_output


@pytest.mark.parametrize(
    "test_name, expected_output",
    [("a", "a"), ("a_b", "a_b"), (" __a^ b^__ ", "a_b"), (",.;:=%_&()_+-a", "__-a")],
)
def test_simplify_under(test_name, expected_output):
    assert dcmdiff.simplify_under(test_name)


@pytest.mark.parametrize(
    "test_description, expected_output",
    [
        ("a", "a"),
        ("a_b", "a_b"),
        (" __a^ b^__ ", "___a__b____"),
        (",.;:=%^&()_+-a", "__-a"),
    ],
)
def test_simplify_series(test_description, expected_output):
    assert dcmdiff.simplify_series(test_description) == expected_output


def test_read_tag_file_no_file(tmp_path, capsys):

    tag_to_comp_fp = tmp_path / "tags.txt"

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        dcmdiff.read_tag_file(tag_to_comp_fp)

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "ERROR: %s does not exist, exiting\n" % tag_to_comp_fp


def test_read_tag_file_no_tags(tmp_path, capsys):

    tag_to_comp_fp = tmp_path / "tags.txt"
    tag_to_comp_fp.touch()

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        dcmdiff.read_tag_file(tag_to_comp_fp)

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "ERROR: no tags found in %s, exiting\n" % tag_to_comp_fp


def test_read_tag_file(tmp_path, capsys):

    tag_to_comp_fp = tmp_path / "tags.txt"
    tag_to_comp_fp.touch()

    with open(tag_to_comp_fp, "w") as f:
        f.writelines(["RepetitionTime\n", "0x00100010\n", "EchTime\n"])

    tc_list = dcmdiff.read_tag_file(tag_to_comp_fp)

    assert tc_list == [("0018", "0080"), ("0010", "0010")]

    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        captured.err
        == "WARNING: Unable to create an element tag from 'EchTime': unknown DICOM element keyword or an invalid int\n"
    )


def test_append_if_dicom(tmp_path):

    fp_not_file = tmp_path / "file_not_exist"
    fp_not_dicom = tmp_path / "not_dicom"
    fp_not_dicom.touch()

    fp_1 = tmp_path / "test_1.dcm"
    ds_1 = pydicom.dataset.Dataset()
    ds_1.StudyDate = "20220101"
    ds_1.PatientBirthDate = "19800101"
    ds_1.PerformedProcedureStepDescription = "MRI Head"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC12345678"
    ds_1.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_1.file_meta = pydicom.dataset.FileMetaDataset()
    ds_1.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_1.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_1.file_meta.ImplementationVersionName = "report"
    ds_1.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_1.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    ds_1.is_implicit_VR = False
    ds_1.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_1.file_meta)
    ds_1.save_as(fp_1, write_like_original=False)

    fp_2 = tmp_path / "test_2.dcm"
    ds_2 = pydicom.dataset.Dataset()
    ds_2.StudyDate = "20220101"
    ds_2.PatientBirthDate = "19800101"
    ds_2.PerformedProcedureStepDescription = "MRI Head"
    ds_2.PatientName = "SURNAME^Firstname"
    ds_2.PatientID = "EFG987654321"
    ds_2.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_2.file_meta = pydicom.dataset.FileMetaDataset()
    ds_2.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_2.file_meta.MediaStorageSOPInstanceUID = "4.5.6.7"
    ds_2.file_meta.ImplementationVersionName = "report"
    ds_2.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_2.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    ds_2.is_implicit_VR = False
    ds_2.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_1.file_meta)
    ds_2.save_as(fp_2, write_like_original=False)

    fs = FileSet()
    fp_3 = tmp_path / "DICOMDIR"
    fs.write(tmp_path)

    # try adding a missing file
    ds_list = dcmdiff.append_if_dicom(fp_not_file, [])
    assert ds_list == []

    # then add a DICOM
    ds_list = dcmdiff.append_if_dicom(fp_1, ds_list)
    assert ds_list == [ds_1]

    # try adding a file that isn't DICOM
    ds_list = dcmdiff.append_if_dicom(fp_not_dicom, ds_list)
    assert ds_list == [ds_1]

    # then add a DICOM
    ds_list = dcmdiff.append_if_dicom(fp_2, ds_list)
    assert ds_list == [ds_1, ds_2]

    # try adding a DICOMDIR
    ds_list = dcmdiff.append_if_dicom(fp_3, ds_list)
    assert ds_list == [ds_1, ds_2]

    # then add a DICOM
    ds_list = dcmdiff.append_if_dicom(fp_1, ds_list)
    assert ds_list == [ds_1, ds_2, ds_1]


def test_make_ds_list_error_1(tmp_path, capsys):
    fp_not_dicom = tmp_path / "not_dicom"
    fp_not_dicom.touch()

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        dcmdiff.make_ds_list(fp_not_dicom)

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "ERROR: No valid DICOM files found, exiting\n"


def test_make_ds_list_error_2(tmp_path, capsys):
    fp_not_file = tmp_path / "file_not_exist"

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        dcmdiff.make_ds_list(fp_not_file)

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "ERROR: %s is neither a file or directory\n" % fp_not_file


def test_make_ds_list_file(tmp_path):
    fp_1 = tmp_path / "test_1.dcm"
    ds_1 = pydicom.dataset.Dataset()
    ds_1.StudyDate = "20220101"
    ds_1.PatientBirthDate = "19800101"
    ds_1.PerformedProcedureStepDescription = "MRI Head"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC12345678"
    ds_1.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_1.file_meta = pydicom.dataset.FileMetaDataset()
    ds_1.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_1.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_1.file_meta.ImplementationVersionName = "report"
    ds_1.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_1.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    ds_1.is_implicit_VR = False
    ds_1.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_1.file_meta)
    ds_1.save_as(fp_1, write_like_original=False)

    ds_list = dcmdiff.make_ds_list(fp_1)
    assert ds_list == [ds_1]


def test_make_ds_list_dir(tmp_path):

    test_dir = tmp_path / "dir1"
    test_dir.mkdir()

    fp_1 = test_dir / "test_1.dcm"
    ds_1 = pydicom.dataset.Dataset()
    ds_1.StudyDate = "20220101"
    ds_1.PatientBirthDate = "19800101"
    ds_1.PerformedProcedureStepDescription = "MRI Head"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC12345678"
    ds_1.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_1.file_meta = pydicom.dataset.FileMetaDataset()
    ds_1.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_1.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_1.file_meta.ImplementationVersionName = "report"
    ds_1.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_1.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    ds_1.is_implicit_VR = False
    ds_1.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_1.file_meta)
    ds_1.save_as(fp_1, write_like_original=False)

    fp_2 = test_dir / "test_2.dcm"
    ds_2 = pydicom.dataset.Dataset()
    ds_2.StudyDate = "20220101"
    ds_2.PatientBirthDate = "19800101"
    ds_2.PerformedProcedureStepDescription = "MRI Head"
    ds_2.PatientName = "SURNAME^Firstname"
    ds_2.PatientID = "EFG987654321"
    ds_2.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_2.file_meta = pydicom.dataset.FileMetaDataset()
    ds_2.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_2.file_meta.MediaStorageSOPInstanceUID = "4.5.6.7"
    ds_2.file_meta.ImplementationVersionName = "report"
    ds_2.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_2.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    ds_2.is_implicit_VR = False
    ds_2.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_1.file_meta)
    ds_2.save_as(fp_2, write_like_original=False)

    fs = FileSet()
    fs.write(test_dir)

    ds_list = dcmdiff.make_ds_list(test_dir)
    assert ds_list == [ds_1, ds_2]


def test_sort_ds_list():

    # Patient 1, Study A, Series 1, Instance 1
    ds_1 = pydicom.dataset.Dataset()
    ds_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_1.StudyDate = "20220101"
    ds_1.StudyTime = "120000.000000"
    ds_1.Modality = "CT"
    ds_1.StudyDescription = "Study A"
    ds_1.SeriesDescription = "Bone"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC1234567"
    ds_1.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesNumber = 1
    ds_1.InstanceNumber = 1

    # Patient 1, Study A, Series 1, Instance 2
    ds_2 = copy.deepcopy(ds_1)
    ds_2.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_2.InstanceNumber = 2

    # Patient 1, Study A, Series 7, Instance 43
    ds_3 = copy.deepcopy(ds_1)
    ds_3.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_3.SeriesDescription = "Tissue"
    ds_3.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_3.SeriesNumber = 7
    ds_3.InstanceNumber = 43

    # Patient 1, Study B, Series 9, Instance 76
    ds_4 = copy.deepcopy(ds_1)
    ds_4.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_4.StudyTime = "121500.000000"
    ds_4.Modality = "MR"
    ds_4.StudyDescription = "Study B"
    ds_4.SeriesDescription = "T1"
    ds_4.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_4.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_4.SeriesNumber = 9
    ds_4.InstanceNumber = 76

    # Patient 2, Study C, Series 10, Instance 96
    ds_5 = pydicom.dataset.Dataset()
    ds_5.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_5.StudyDate = "20220101"
    ds_5.StudyTime = "120000.000000"
    ds_5.Modality = "MR"
    ds_5.StudyDescription = "Study C"
    ds_5.SeriesDescription = "T2"
    ds_5.PatientName = "OTHERNAME^Firstname"
    ds_5.PatientID = "1234567DEF"
    ds_5.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_5.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_5.SeriesNumber = 10
    ds_5.InstanceNumber = 96

    # note ds_2 is a repeat SOPInstance so it won't end up in the dict
    ds_dict = dcmdiff.sort_ds_list([ds_1, ds_2, ds_2, ds_3, ds_4, ds_5])

    pt_name_1 = str(ds_1.get("PatientName", "unknown"))
    clean_pt_name_1 = dcmdiff.simplify_under(pt_name_1.lower())

    pt_name_2 = str(ds_5.get("PatientName", "unknown"))
    clean_pt_name_2 = dcmdiff.simplify_under(pt_name_2.lower())

    ref_ds_dict = {
        ds_1.PatientID: {
            "patient_name": clean_pt_name_1,
            ds_1.StudyInstanceUID: {
                "study_datetime": "20220101.120000",
                "study_desc": dcmdiff.simplify_series(ds_1.StudyDescription),
                ds_1.SeriesInstanceUID: {
                    "series_num": int(ds_1.SeriesNumber),
                    "modality": ds_1.Modality,
                    "series_desc": dcmdiff.simplify_series(ds_1.SeriesDescription),
                    ds_1.SOPInstanceUID: ds_1,
                    ds_2.SOPInstanceUID: ds_2,
                },
                ds_3.SeriesInstanceUID: {
                    "series_num": int(ds_3.SeriesNumber),
                    "modality": ds_3.Modality,
                    "series_desc": dcmdiff.simplify_series(ds_3.SeriesDescription),
                    ds_3.SOPInstanceUID: ds_3,
                },
            },
            ds_4.StudyInstanceUID: {
                "study_datetime": "20220101.121500",
                "study_desc": dcmdiff.simplify_series(ds_4.StudyDescription),
                ds_4.SeriesInstanceUID: {
                    "series_num": int(ds_4.SeriesNumber),
                    "modality": ds_4.Modality,
                    "series_desc": dcmdiff.simplify_series(ds_4.SeriesDescription),
                    ds_4.SOPInstanceUID: ds_4,
                },
            },
        },
        ds_5.PatientID: {
            "patient_name": clean_pt_name_2,
            ds_5.StudyInstanceUID: {
                "study_datetime": "20220101.120000",
                "study_desc": dcmdiff.simplify_series(ds_5.StudyDescription),
                ds_5.SeriesInstanceUID: {
                    "series_num": int(ds_5.SeriesNumber),
                    "modality": ds_5.Modality,
                    "series_desc": dcmdiff.simplify_series(ds_5.SeriesDescription),
                    ds_5.SOPInstanceUID: ds_5,
                },
            },
        },
    }
    assert ds_dict == ref_ds_dict


def test_get_patient_ds_dict_1pat():

    ds_dict = {"1.2.3.4.5.6": {"patient_name": "surname-firstname"}}
    assert dcmdiff.get_patient_ds_dict(ds_dict) == {"patient_name": "surname-firstname"}


def test_get_patient_ds_dict_2pat(capsys):

    ds_dict = {
        "123456": {"patient_name": "surname-firstname"},
        "78910": {"patient_name": "surname1-firstname1"},
    }

    with mock.patch.object(builtins, "input", lambda _: "0"):
        ds_pat_dict = dcmdiff.get_patient_ds_dict(ds_dict)
        captured = capsys.readouterr()
        assert "   0 - 123456-surname-firstname" in captured.out
        assert "   1 - 78910-surname1-firstname1" in captured.out
        assert ds_pat_dict == {"patient_name": "surname-firstname"}


def test_get_study_ds_dict_1study():

    ds_dict = {
        "patient_name": "surname-firstname",
        "1.2.3.4.5.6": {"study_datetime": "20220101.120000", "study_desc": "study_a"},
    }
    assert dcmdiff.get_study_ds_dict(ds_dict) == {
        "study_datetime": "20220101.120000",
        "study_desc": "study_a",
    }


def test_get_study_ds_dict_2study(capsys):

    ds_dict = {
        "patient_name": "surname-firstname",
        "1.2.3.4.5.6": {"study_datetime": "20220101.120000", "study_desc": "study_a"},
        "5.6.7.7.9.10": {"study_datetime": "20220202.130000", "study_desc": "study_b"},
    }

    with mock.patch.object(builtins, "input", lambda _: "1"):
        ds_study_dict = dcmdiff.get_study_ds_dict(ds_dict)
        captured = capsys.readouterr()
        assert "   0 - 20220101.120000-study_a" in captured.out
        assert "   1 - 20220202.130000-study_b" in captured.out
        assert ds_study_dict == {
            "study_datetime": "20220202.130000",
            "study_desc": "study_b",
        }


def test_get_all_series_details(tmp_path):

    test_dir = tmp_path / "test_study"
    test_dir.mkdir()
    fp_1 = test_dir / "01.dcm"
    fp_2 = test_dir / "02.dcm"
    fp_3 = test_dir / "03.dcm"

    # Patient 1, Study A, Series 1, Instance 1
    ds_1 = pydicom.dataset.Dataset()
    ds_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_1.StudyDate = "20220101"
    ds_1.StudyTime = "120000.000000"
    ds_1.Modality = "CT"
    ds_1.StudyDescription = "Study A"
    ds_1.SeriesDescription = "Bone"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC1234567"
    ds_1.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesNumber = 1
    ds_1.InstanceNumber = 1
    ds_1.file_meta = pydicom.dataset.FileMetaDataset()
    ds_1.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_1.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_1.file_meta.ImplementationVersionName = "report"
    ds_1.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_1.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    ds_1.is_implicit_VR = False
    ds_1.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_1.file_meta)
    ds_1.save_as(fp_1, write_like_original=False)

    # Patient 1, Study A, Series 1, Instance 2
    ds_2 = copy.deepcopy(ds_1)
    ds_2.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_2.InstanceNumber = 2
    ds_2.is_implicit_VR = False
    ds_2.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_2.file_meta)
    ds_2.save_as(fp_2, write_like_original=False)

    # Patient 1, Study A, Series 7, Instance 43
    ds_3 = copy.deepcopy(ds_1)
    ds_3.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_3.SeriesDescription = "Tissue"
    ds_3.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_3.SeriesNumber = 7
    ds_3.InstanceNumber = 43
    ds_3.is_implicit_VR = False
    ds_3.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_3.file_meta)
    ds_3.save_as(fp_3, write_like_original=False)

    series_details = dcmdiff.get_all_series_details(test_dir)

    ref_series_details = [
        (
            ds_1.SeriesInstanceUID,
            ds_1.SeriesNumber,
            ds_1.Modality,
            ds_1.SeriesDescription,
            {
                "series_num": ds_1.SeriesNumber,
                "modality": ds_1.Modality,
                "series_desc": ds_1.SeriesDescription,
                ds_1.SOPInstanceUID: ds_1,
                ds_2.SOPInstanceUID: ds_2,
            },
        ),
        (
            ds_3.SeriesInstanceUID,
            ds_3.SeriesNumber,
            ds_3.Modality,
            ds_3.SeriesDescription,
            {
                "series_num": ds_3.SeriesNumber,
                "modality": ds_3.Modality,
                "series_desc": ds_3.SeriesDescription,
                ds_3.SOPInstanceUID: ds_3,
            },
        ),
    ]

    assert series_details == ref_series_details


def test_choose_series(capsys):

    series_list = [
        (
            "1.2.3.4.5",
            1,
            "MR",
            "T1",
            {
                "series_num": 1,
                "modality": "MR",
                "series_desc": "T1",
                "A.B.C.D.E": "ds1",
                "F.G.H.I.J": "ds2",
            },
        ),
        (
            "2.3.4.5.6",
            2000,
            "DOC",
            "Results",
            {
                "series_num": 2000,
                "modality": "DOC",
                "series_desc": "Results",
                "K.L.M.N.O": "ds2",
            },
        ),
    ]

    with mock.patch.object(builtins, "input", lambda _: "1"):
        series_dict = dcmdiff.choose_series(series_list)
        captured = capsys.readouterr()
        assert "   0 - 0001-MR-T1" in captured.out
        assert "   1 - 2000-DOC-Results" in captured.out

        assert series_dict == {
            "series_num": 2000,
            "modality": "DOC",
            "series_desc": "Results",
            "K.L.M.N.O": "ds2",
        }

    with mock.patch.object(builtins, "input", lambda _: "n"):
        series_dict = dcmdiff.choose_series(series_list)
        captured = capsys.readouterr()
        assert "   0 - 0001-MR-T1" in captured.out
        assert "   1 - 2000-DOC-Results" in captured.out
        assert not series_dict


def test_find_matching_series(capsys):

    series_list = [
        (
            "1.2.3.4.5",
            1,
            "MR",
            "T1",
            {
                "series_num": 1,
                "modality": "MR",
                "series_desc": "T1",
                "A.B.C.D.E": "ds1",
                "F.G.H.I.J": "ds2",
            },
        ),
        (
            "2.3.4.5.6",
            2000,
            "DOC",
            "Results",
            {
                "series_num": 2000,
                "modality": "DOC",
                "series_desc": "Results",
                "K.L.M.N.O": "ds2",
            },
        ),
    ]

    with mock.patch.object(builtins, "input", lambda _: "1"):
        matching_series = dcmdiff.find_matching_series("DOC", "Resalts", series_list)
        captured = capsys.readouterr()
        assert (
            "*** No series with matching Modality and Series Description found. Would you like to pick one?"
            in captured.out
        )
        assert "   0 - 0001-MR-T1" in captured.out
        assert "   1 - 2000-DOC-Results" in captured.out

        assert matching_series == {
            "series_num": 2000,
            "modality": "DOC",
            "series_desc": "Results",
            "K.L.M.N.O": "ds2",
        }

    assert dcmdiff.find_matching_series("DOC", "Results", series_list) == {
        "series_num": 2000,
        "modality": "DOC",
        "series_desc": "Results",
        "K.L.M.N.O": "ds2",
    }

    series_list.append(
        (
            "2.3.4.5.6",
            3000,
            "DOC",
            "Results",
            {
                "series_num": 3000,
                "modality": "DOC",
                "series_desc": "Results",
                "K.L.M.N.O": "ds3",
            },
        ),
    )

    with mock.patch.object(builtins, "input", lambda _: "1"):
        matching_series = dcmdiff.find_matching_series("DOC", "Results", series_list)
        captured = capsys.readouterr()
        assert (
            "2 series with matching Modality and Series Description found:"
            in captured.out
        )
        assert "   0 - 2000-DOC-Results" in captured.out
        assert "   1 - 3000-DOC-Results" in captured.out

        assert matching_series == {
            "series_num": 3000,
            "modality": "DOC",
            "series_desc": "Results",
            "K.L.M.N.O": "ds3",
        }


def test_choose_instance(capsys):

    ds_1 = pydicom.dataset.Dataset()
    ds_1.InstanceNumber = 1

    ds_2 = pydicom.dataset.Dataset()
    ds_2.InstanceNumber = 2

    ds_3 = pydicom.dataset.Dataset()
    ds_3.InstanceNumber = 3

    instance_list = [ds_1, ds_2, ds_3]

    with mock.patch.object(builtins, "input", lambda _: "1"):
        ds_test = dcmdiff.choose_instance(instance_list)
        captured = capsys.readouterr()
        assert "   0 - instance number 0001" in captured.out
        assert "   1 - instance number 0002" in captured.out
        assert "   2 - instance number 0003" in captured.out

        assert ds_test == ds_2

    with mock.patch.object(builtins, "input", lambda _: "n"):
        ds_test = dcmdiff.choose_instance(instance_list)
        captured = capsys.readouterr()
        assert "   0 - instance number 0001" in captured.out
        assert "   1 - instance number 0002" in captured.out
        assert "   2 - instance number 0003" in captured.out
        assert not ds_test


def test_find_matching_instance(capsys):

    ds_1 = pydicom.dataset.Dataset()
    ds_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_1.InstanceNumber = 1

    ds_2 = pydicom.dataset.Dataset()
    ds_2.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_2.InstanceNumber = 1

    ds_3 = pydicom.dataset.Dataset()
    ds_3.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_3.InstanceNumber = 3

    # case where no matches but only one instance in test series
    test_uid_dict = {
        "series_num": 1,
        "modality": "MR",
        "series_desc": "T1",
        ds_1.SOPInstanceUID: ds_1,
    }
    ds_result = dcmdiff.find_matching_instance(4, test_uid_dict)
    assert ds_result == ds_1

    # case where no matches and multiple instances in test series
    test_uid_dict = {
        "series_num": 1,
        "modality": "MR",
        "series_desc": "T1",
        ds_1.SOPInstanceUID: ds_1,
        ds_2.SOPInstanceUID: ds_2,
        ds_3.SOPInstanceUID: ds_3,
    }

    ds_result_2 = dcmdiff.find_matching_instance(4, test_uid_dict)
    assert not ds_result_2

    # case with one match
    ds_result_3 = dcmdiff.find_matching_instance(3, test_uid_dict)
    assert ds_result_3 == ds_3

    # case with multiple matches
    with mock.patch.object(builtins, "input", lambda _: "1"):
        ds_result_4 = dcmdiff.find_matching_instance(1, test_uid_dict)
        captured = capsys.readouterr()
        assert "   0 - instance number 0001" in captured.out
        assert "   1 - instance number 0001" in captured.out
        assert ds_result_4 == ds_2


def test_keep_tags():
    ds_1 = pydicom.dataset.Dataset()
    ds_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_1.StudyDate = "20220101"
    ds_1.StudyTime = "120000.000000"
    ds_1.Modality = "CT"
    ds_1.StudyDescription = "Study A"
    ds_1.SeriesDescription = "Bone"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC1234567"
    ds_1.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesNumber = 1
    ds_1.InstanceNumber = 1

    ds_1 = dcmdiff.keep_tags(
        ds_1, [pydicom.tag.Tag("0x00100010"), pydicom.tag.Tag("0x00100020")]
    )

    ds_remove_ref = pydicom.dataset.Dataset()
    ds_remove_ref.PatientName = "SURNAME^Firstname"
    ds_remove_ref.PatientID = "ABC1234567"

    assert ds_1 == ds_remove_ref


def test_remove_tags():
    ds_1 = pydicom.dataset.Dataset()
    ds_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_1.StudyDate = "20220101"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC1234567"

    ds_1 = dcmdiff.remove_tags(
        ds_1, [pydicom.tag.Tag("SOPInstanceUID"), pydicom.tag.Tag("StudyDate")]
    )

    ds_remove_ref = pydicom.dataset.Dataset()
    ds_remove_ref.PatientName = "SURNAME^Firstname"
    ds_remove_ref.PatientID = "ABC1234567"

    assert ds_1 == ds_remove_ref


def test_remove_vr_tags():
    ds_1 = pydicom.dataset.Dataset()
    ds_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_1.StudyDate = "20220101"
    ds_1.StudyTime = "120000.000000"
    ds_1.Modality = "CT"
    ds_1.StudyDescription = "Study A"
    ds_1.SeriesDescription = "Bone"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC1234567"
    ds_1.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesNumber = 1
    ds_1.InstanceNumber = 1

    ds_1 = dcmdiff.remove_vr_tags(ds_1, ["UI", "PN", "DT", "DA", "TM"])

    ds_without_vr_ref = pydicom.dataset.Dataset()
    ds_without_vr_ref.Modality = "CT"
    ds_without_vr_ref.StudyDescription = "Study A"
    ds_without_vr_ref.SeriesDescription = "Bone"
    ds_without_vr_ref.PatientID = "ABC1234567"
    ds_without_vr_ref.SeriesNumber = 1
    ds_without_vr_ref.InstanceNumber = 1

    assert ds_1 == ds_without_vr_ref


def test_remove_group_tags():
    ds_1 = pydicom.dataset.Dataset()
    ds_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_1.StudyDate = "20220101"
    ds_1.StudyTime = "120000.000000"
    ds_1.Modality = "CT"
    ds_1.StudyDescription = "Study A"
    ds_1.SeriesDescription = "Bone"
    ds_1.PatientName = "SURNAME^Firstname"
    ds_1.PatientID = "ABC1234567"
    ds_1.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_1.SeriesNumber = 1
    ds_1.InstanceNumber = 1

    ds_1 = dcmdiff.remove_group_tags(ds_1, ["0x0010", "0x0020"])

    ds_without_group10_20_ref = pydicom.dataset.Dataset()
    ds_without_group10_20_ref.SOPInstanceUID = ds_1.SOPInstanceUID
    ds_without_group10_20_ref.StudyDate = "20220101"
    ds_without_group10_20_ref.StudyTime = "120000.000000"
    ds_without_group10_20_ref.Modality = "CT"
    ds_without_group10_20_ref.StudyDescription = "Study A"
    ds_without_group10_20_ref.SeriesDescription = "Bone"
    # ds_without_group10_20_ref.StudyInstanceUID = ds_1.StudyInstanceUID
    # ds_without_group10_20_ref.SeriesInstanceUID = ds_1.SeriesInstanceUID
    # ds_without_group10_20_ref.InstanceNumber = 1

    assert ds_1 == ds_without_group10_20_ref


def test_tags_to_list():

    ds = pydicom.dataset.Dataset()
    ds.PatientName = "SURNAME^Firstname"
    ds.PatientID = "ABC1234567"
    ds.SeriesNumber = 1
    ds.InstanceNumber = 1

    tag_list = dcmdiff.tags_to_list(ds)

    ref_tag_list = [
        "(0010, 0010) Patient's Name                      PN: 'SURNAME^Firstname'\n",
        "(0010, 0020) Patient ID                          LO: 'ABC1234567'\n",
        "(0020, 0011) Series Number                       IS: '1'\n",
        "(0020, 0013) Instance Number                     IS: '1'",
    ]

    assert tag_list == ref_tag_list


SCRIPT_NAME = "dcmdiff"
SCRIPT_USAGE = f"usage: {SCRIPT_NAME} [-h]"


def test_prints_help_1(script_runner):
    result = script_runner.run(SCRIPT_NAME)
    assert result.success
    assert result.stdout.startswith(SCRIPT_USAGE)


def test_prints_help_2(script_runner):
    result = script_runner.run(SCRIPT_NAME, "-h")
    assert result.success
    assert result.stdout.startswith(SCRIPT_USAGE)


def test_prints_help_for_invalid_option(script_runner):
    result = script_runner.run(SCRIPT_NAME, "-!")
    assert not result.success
    assert result.stderr.startswith(SCRIPT_USAGE)


def test_dcmdiff_single_files(tmp_path, script_runner):

    fp_r = tmp_path / "ref.dcm"
    ds_r = pydicom.dataset.Dataset()
    ds_r.StudyDate = "20220101"
    ds_r.PatientBirthDate = "19800101"
    ds_r.PatientName = "SURNAME^Firstname"
    ds_r.PatientID = "ABC12345678"
    ds_r.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_r.SeriesDescription = "T1"
    ds_r.RepetitionTime = 1000
    ds_r.Modality = "MR"
    ds_r.SeriesNumber = 10
    ds_r.InstanceNumber = 1
    ds_r.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_r.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_r.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_r.file_meta = pydicom.dataset.FileMetaDataset()
    ds_r.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_r.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_r.file_meta.ImplementationVersionName = "report"
    ds_r.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_r.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"

    ds_r.is_implicit_VR = False
    ds_r.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_r.file_meta)
    ds_r.save_as(fp_r, write_like_original=False)

    fp_t = tmp_path / "test.dcm"
    ds_t = copy.deepcopy(ds_r)
    ds_t.RepetitionTime = 2000
    ds_t.save_as(fp_t, write_like_original=False)

    output_dir = tmp_path / "htmldiff"

    result = script_runner.run(SCRIPT_NAME, str(fp_r), str(fp_t), "-o", str(output_dir))
    assert result.success
    assert output_dir.is_dir()

    fp_study_html = output_dir / "study_index.html"
    assert fp_study_html.is_file()

    fp_series_html = output_dir / "0010-MR-T1.html"
    assert fp_series_html.is_file()

    fp_inst_html = output_dir / ("%s.html" % ds_r.SOPInstanceUID)
    assert fp_inst_html.is_file()

    ref_study_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>DICOM Study</h1>\n",
        "<p>Select a reference series to view differences:</p>\n",
        '<ol type= "1">\n',
        '<li><a href="%s">0010-MR-T1</a></li>\n' % str(fp_series_html),
        "</ol>\n",
        "</body>\n",
        "</html>",
    ]

    ref_series_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>Reference series: 0010-MR-T1</h1>\n",
        "<h1>Test series: 0010-MR-T1</h1>\n",
        "<p>Select an instance to view differences:</p>\n",
        '<ol type= "1">\n',
        '<li><a href="%s">%s</a></li>\n' % (str(fp_inst_html), ds_r.SOPInstanceUID),
        "</ol>\n",
        "</body>\n",
        "</html>",
    ]

    with open(fp_study_html, "r") as f:
        study_contents = f.readlines()

    assert study_contents == ref_study_contents

    with open(fp_series_html, "r") as f:
        series_contents = f.readlines()

    assert series_contents == ref_series_contents


def test_dcmdiff_dirs_no_match_ser(tmp_path, script_runner):

    ref_dp = tmp_path / "ref"
    ref_dp.mkdir()

    test_dp = tmp_path / "test"
    test_dp.mkdir()

    fp_r = ref_dp / "ref.dcm"
    ds_r = pydicom.dataset.Dataset()
    ds_r.StudyDate = "20220101"
    ds_r.PatientBirthDate = "19800101"
    ds_r.PatientName = "SURNAME^Firstname"
    ds_r.PatientID = "ABC12345678"
    ds_r.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_r.SeriesDescription = "T1"
    ds_r.Modality = "MR"
    ds_r.SeriesNumber = 10
    ds_r.InstanceNumber = 1
    ds_r.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_r.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_r.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_r.file_meta = pydicom.dataset.FileMetaDataset()
    ds_r.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_r.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_r.file_meta.ImplementationVersionName = "report"
    ds_r.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_r.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"

    ds_r.is_implicit_VR = False
    ds_r.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_r.file_meta)
    ds_r.save_as(fp_r, write_like_original=False)

    fp_t_1 = test_dp / "test.dcm"
    ds_t_1 = copy.deepcopy(ds_r)
    ds_t_1.SeriesDescription = "BONE"
    ds_t_1.Modality = "CT"
    ds_t_1.SeriesNumber = 9
    ds_t_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_t_1.save_as(fp_t_1, write_like_original=False)

    output_dir = tmp_path / "htmldiff"
    output_dir.mkdir()

    # chose not to select a series when no matches found automatically
    with mock.patch.object(builtins, "input", lambda _: "n"):
        result = script_runner.run(
            SCRIPT_NAME,
            str(ref_dp),
            str(test_dp),
            "-o",
            str(output_dir),
        )

    assert result.success
    assert output_dir.is_dir()

    fp_study_html = output_dir / "study_index.html"
    assert fp_study_html.is_file()

    fp_series_html = output_dir / "0010-MR-T1.html"
    assert fp_series_html.is_file()

    fp_inst_html = output_dir / ("%s.html" % ds_r.SOPInstanceUID)
    assert not fp_inst_html.is_file()

    ref_study_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>DICOM Study</h1>\n",
        "<p>Select a reference series to view differences:</p>\n",
        '<ol type= "1">\n',
        '<li><a href="%s">0010-MR-T1</a></li>\n' % str(fp_series_html),
        "</ol>\n",
        "</body>\n",
        "</html>",
    ]

    ref_series_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>Reference series: 0010-MR-T1</h1>\n",
        "<p>No series from test study selected for comparison</p>\n",
        "</body>\n",
        "</html>",
    ]

    with open(fp_study_html, "r") as f:
        study_contents = f.readlines()

    assert study_contents == ref_study_contents

    with open(fp_series_html, "r") as f:
        series_contents = f.readlines()

    assert series_contents == ref_series_contents


def test_dcmdiff_dirs_no_match_inst(tmp_path, script_runner):

    ref_dp = tmp_path / "ref"
    ref_dp.mkdir()

    test_dp = tmp_path / "test"
    test_dp.mkdir()

    fp_r = ref_dp / "ref.dcm"
    ds_r = pydicom.dataset.Dataset()
    ds_r.StudyDate = "20220101"
    ds_r.PatientBirthDate = "19800101"
    ds_r.PatientName = "SURNAME^Firstname"
    ds_r.PatientID = "ABC12345678"
    ds_r.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_r.SeriesDescription = "T1"
    ds_r.Modality = "MR"
    ds_r.SeriesNumber = 10
    ds_r.InstanceNumber = 11
    ds_r.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_r.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_r.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_r.file_meta = pydicom.dataset.FileMetaDataset()
    ds_r.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_r.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_r.file_meta.ImplementationVersionName = "report"
    ds_r.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_r.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"

    ds_r.is_implicit_VR = False
    ds_r.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_r.file_meta)
    ds_r.save_as(fp_r, write_like_original=False)

    fp_t_1 = test_dp / "test.dcm"
    ds_t_1 = copy.deepcopy(ds_r)
    ds_t_1.InstanceNumber = 1
    ds_t_1.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_t_1.save_as(fp_t_1, write_like_original=False)

    fp_t_2 = test_dp / "test_2.dcm"
    ds_t_2 = copy.deepcopy(ds_r)
    ds_t_2.InstanceNumber = 2
    ds_t_2.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_t_2.save_as(fp_t_2, write_like_original=False)

    output_dir = tmp_path / "htmldiff"
    output_dir.mkdir()

    # no matching instance number
    result = script_runner.run(
        SCRIPT_NAME, str(ref_dp), str(test_dp), "-o", str(output_dir)
    )

    assert result.success
    assert output_dir.is_dir()

    fp_study_html = output_dir / "study_index.html"
    assert fp_study_html.is_file()

    fp_series_html = output_dir / "0010-MR-T1.html"
    assert fp_series_html.is_file()

    fp_inst_html = output_dir / ("%s.html" % ds_r.SOPInstanceUID)
    assert fp_inst_html.is_file()

    ref_study_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>DICOM Study</h1>\n",
        "<p>Select a reference series to view differences:</p>\n",
        '<ol type= "1">\n',
        '<li><a href="%s">0010-MR-T1</a></li>\n' % str(fp_series_html),
        "</ol>\n",
        "</body>\n",
        "</html>",
    ]

    ref_series_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>Reference series: 0010-MR-T1</h1>\n",
        "<h1>Test series: 0010-MR-T1</h1>\n",
        "<p>Select an instance to view differences:</p>\n",
        '<ol type= "1">\n',
        '<li><a href="%s">%s</a></li>\n' % (str(fp_inst_html), ds_r.SOPInstanceUID),
        "</ol>\n",
        "</body>\n",
        "</html>",
    ]

    ref_inst_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>Instance %s</h1>\n" % ds_r.SOPInstanceUID,
        "<p>No instance from test series found or selected for comparison</p>\n",
        "</body>\n",
        "</html>",
    ]

    with open(fp_study_html, "r") as f:
        study_contents = f.readlines()

    assert study_contents == ref_study_contents

    with open(fp_series_html, "r") as f:
        series_contents = f.readlines()

    assert series_contents == ref_series_contents

    with open(fp_inst_html, "r") as f:
        inst_contents = f.readlines()

    assert inst_contents == ref_inst_contents


def test_dcmdiff_single_remove_tags(tmp_path, script_runner):

    fp_r = tmp_path / "ref.dcm"
    ds_r = pydicom.dataset.Dataset()
    ds_r.StudyDate = "20220101"
    ds_r.PatientBirthDate = "19800101"
    ds_r.PatientName = "SURNAME^Firstname"
    ds_r.PatientID = "ABC12345678"
    ds_r.ReferringPhysicianName = "DrSURNAME^DrFirstname"
    ds_r.SeriesDescription = "T1"
    ds_r.RepetitionTime = 1000
    ds_r.Modality = "MR"
    ds_r.SeriesNumber = 10
    ds_r.InstanceNumber = 1
    ds_r.StudyInstanceUID = pydicom.uid.generate_uid()
    ds_r.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds_r.SOPInstanceUID = pydicom.uid.generate_uid()
    ds_r.file_meta = pydicom.dataset.FileMetaDataset()
    ds_r.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds_r.file_meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds_r.file_meta.ImplementationVersionName = "report"
    ds_r.file_meta.ImplementationClassUID = "1.2.3.4"
    ds_r.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"

    ds_r.is_implicit_VR = False
    ds_r.is_little_endian = True
    pydicom.dataset.validate_file_meta(ds_r.file_meta)
    ds_r.save_as(fp_r, write_like_original=False)

    fp_t = tmp_path / "test.dcm"
    ds_t = copy.deepcopy(ds_r)
    ds_t.RepetitionTime = 2000
    ds_t.save_as(fp_t, write_like_original=False)

    output_dir = tmp_path / "htmldiff"

    tags_fp = tmp_path / "tags.txt"
    tags_fp.touch()

    with open(tags_fp, "w") as f:
        f.writelines(["RepetitionTime\n", "0x00100010\n"])

    result = script_runner.run(
        SCRIPT_NAME,
        str(fp_r),
        str(fp_t),
        "-o",
        str(output_dir),
        "-c",
        str(tags_fp),
        "--compare-one-inst",
        "--ignore-private",
        "--ignore-vr",
        "UI",
        "DT",
        "--ignore-group",
        "0x0010",
        "--ignore-tag",
        "Rows",
        "SeriesNumber",
    )
    assert result.success
    assert output_dir.is_dir()

    fp_study_html = output_dir / "study_index.html"
    assert fp_study_html.is_file()

    fp_series_html = output_dir / "0010-MR-T1.html"
    assert fp_series_html.is_file()

    fp_inst_html = output_dir / ("%s.html" % ds_r.SOPInstanceUID)
    assert fp_inst_html.is_file()

    ref_study_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>DICOM Study</h1>\n",
        "<p>Select a reference series to view differences:</p>\n",
        '<ol type= "1">\n',
        '<li><a href="%s">0010-MR-T1</a></li>\n' % str(fp_series_html),
        "</ol>\n",
        "</body>\n",
        "</html>",
    ]

    ref_series_contents = [
        "<!DOCTYPE html>\n",
        "<html>\n",
        "<body>\n",
        "<h1>Reference series: 0010-MR-T1</h1>\n",
        "<h1>Test series: 0010-MR-T1</h1>\n",
        "<p>Select an instance to view differences:</p>\n",
        '<ol type= "1">\n',
        '<li><a href="%s">%s</a></li>\n' % (str(fp_inst_html), ds_r.SOPInstanceUID),
        "</ol>\n",
        "</body>\n",
        "</html>",
    ]

    with open(fp_study_html, "r") as f:
        study_contents = f.readlines()

    assert study_contents == ref_study_contents

    with open(fp_series_html, "r") as f:
        series_contents = f.readlines()

    assert series_contents == ref_series_contents
