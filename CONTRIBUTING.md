# Contributing

This is a personal project, hence contributions aren't expected. 
This guide is intended to be a reference for myself.

## Developing

1. Activate the virtual environment in which `tox` is installed

    ```bash
    source dcmdiff-tox-env/bin/activate
    ```
   
2. Call `tox` to check the formatting and style (`isort`, `black` and `flake8`)
 run the tests, and check testing coverage:

    ```bash
    tox
    ```

3. Make your changes and modify the appropriate tests 

4. Auto-format the code with `isort` and `black` using `tox`:

    ```bash
    tox -e format
    ```

5. Create and activate a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/#creating-a-virtual-environment) for [development](https://tox.readthedocs.io/en/latest/example/devenv.html):

    ```bash
    tox --devenv venv
    source venv/bin/activate
    ```

5. Run the tests:

    ```bash
    pytest -v
    ```

6. If all the tests pass re-activate the the virtual environment in which tox 
is installed

    ```bash
    source dcmdiff-tox-env/bin/activate
    ```

7. Repeat step 2 i.e. call `tox` to check the formatting and style run the 
tests, and check testing coverage:

    ```bash
    tox
    ```

## Releasing

1. Commit your changes:

    ```bash
    git commit -a
    ```

2. Choose a version number e.g.:

    ```bash
    version=release-1.1.0
    ```

3. Update the [changelog](./CHANGELOG.md):

    ```bash
    git commit -a -m "Update changelog for $version"
    ```

4. Tag the release:

    ```bash
    git tag -a $version -m "release $version"
    ```

5. Push the changes to the GitHub repository

    ```bash
    git push -u origin main --follow-tags
    ```

6. Create the [source distribution](https://packaging.python.org/glossary/#term-Source-Distribution-or-sdist) and [wheel](https://packaging.python.org/glossary/#term-Built-Distribution) packages:

    ```bash
    tox -e release
    ```
   
   This creates a `.whl` and `.tar.gz` file in `dist` directory - these can be 
   uploaded to GitHub in the Release section and installed locally (see below).
   
## Local Install

1. Create a directory to store the package e.g. 

    ```bash
    mkdir dcmdiff
    ```

2. Create a new virtual environment in which to install `dcmdiff`

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
    pip install <PATH-TO-WHL> 
    ```