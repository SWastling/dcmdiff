# Contributing

This is a personal project, hence contributions aren't expected. 
This guide is intended to be a reference for myself.

## Developing

1. Clone the repository from [GitHub](https://github.com/):

    ```bash
    git clone https://github.com/SWastling/dcmdiff.git
    ``` 

2. Check `dcmdiff` runs using:

    ```bash
    uv run dcmdiff
    ```

3. Make your changes and modify the appropriate tests 

4. Lint and format with `ruff`:

    ```bash
    uv run ruff check --fix
    uv run ruff format
    ```

5. Run the tests and check their coverage:

    ```bash
    uv run coverage run -m pytest
    uv run coverage html
    firefox htmlcov/index.html
    ```

## Releasing
1. Update the date in `LICENSE`

    ```bash
    git add LICENSE
    git commit -m "Update date in LICENSE"
    ```

2. Bump the version number in `pyproject.toml` e.g. `1.0.1`.

    ```bash
    git add pyproject.toml
    git commit -m "Bump the version number in pyproject.toml"
    ```

3. Update the `CHANGELOG.md` file

4. Commit the changes to git repository:

    ```bash
    git commit -a -m "Update changelog for 1.0.1"
    ```

5. Tag the release in the git repository:

    ```bash
    git tag -a $version -m "release 1.0.1"
    ```

6. Build the package for distribution:

    ```bash
    uv build
    ```

7. Push the local changes to the remote repository on [GitHub](https://github.com/) 
    
    ```bash
    git push -u origin main --follow-tags
    ```

8. Create a release on [GitHub](https://github.com/) using the following instructions https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository

9. Upload the `.whl` and `.tar.gz` files from the `dist` directory to the release section on [GitHub](https://github.com/)