# dcmdiff

## Synopsis
Find differences between DICOM instances, series or studies

## Usage

```bash
dcmdiff [options] r t
```
- `r`: reference DICOM file or directory
- `t`: test DICOM file or directory

## Options
- `-h`: display help message
- `-o`: output directory (default ./htmldiff)
- `-c`: file containing list of DICOM tags to compare in the reference and test 
DICOM files. Tags can be keywords e.g. RepetitionTime or combined group and 
element numbers e.g. 0x00180080. For example the file could include:
    ```bash
    Modality
    SliceThickness
    RepetitionTime
    EchoTime
    Rows
    Columns
    PixelSpacing
    0x0025101b
    ```
    See also the an [example](./example_tags_to_compare.txt) file.
- `-context`: produce a context format diff (default: False, i.e. full files shown)
- `-l`: number of context lines (default: 1)
- `--compare-one-inst`: only compare one instance per series
- `--ignore-private`: ignore all elements with an odd group number
- `--ignore-vr`: list of value-representations to ignore (e.g. AS, AT, CS, 
DA, DS, DT, FL, FD, IS, LO, LT, OB, OD, OF, OW, PN, SH, SL, SQ, SS, ST, TM, UI, 
UL, UN, US or UT)
- `--ignore-group`: list of groups to ignore (e.g. 0x0008 or 0x0010)
- `--ignore-tag`: list of tags to ignore. Tags can be keywords e.g. 
RepetitionTime or combined group and element numbers e.g. 0x00180080
- `--version`: show version

## Description
dcmdiff attempts to find the differences between two DICOM files or two 
directories containing DICOM files. The output is a side-by-side diff in an 
HTML file. In the case of input directories containing DICOM files 
the user is prompted to select the PATIENT and then the STUDY of interest to 
compare. For this PATIENT and STUDY dcmdiff attempts to match up SERIES in 
the `reference` and `test` using the Modality and Series Description. If no match
is found the user is asked to match series manually. All the attributes within 
each INSTANCE in each SERIES are compared. The user can chose to ignore private 
tags, elements with a given VR, elements in a particular group or specific tags. 
They can also provide a list of tags to compare.

## Installing
1. Create a directory to store the package e.g.:

    ```bash
    mkdir dcmdiff
    ```

2. Create a new virtual environment in which to install `dcmdiff`:

    ```bash
    python3 -m venv dcmdiff-env
    ```
   
3. Activate the virtual environment:

    ```bash
    source dcmdiff-env/bin/activate
    ```

4. Upgrade `pip` and `build`:

    ```bash
    pip install --upgrade pip
    pip install --upgrade build
    ```

5. Install using `pip`:
    ```bash
    pip install git+https://github.com/SWastling/dcmdiff.git
    ```

## License
See [MIT license](./LICENSE)


## Authors and Acknowledgements
[Dr Stephen Wastling](mailto:stephen.wastling@nhs.net)

